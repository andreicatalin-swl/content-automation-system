import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import imageio_ffmpeg
import numpy as np

from content_automation_system.artifacts.artifact import Artifact, Kind
from content_automation_system.artifacts.artifact_manager import ArtifactManager
from content_automation_system.content_agent.nodes.join_videos import (
    JoinVideos,
    VideoJoiningInput,
)


class JoinVideosIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.manager = ArtifactManager(Path(self.directory.name))
        self.node = JoinVideos(self.manager, 'joined', Kind.TEMPORARY)

    def clip(self, name, size, color, fps=10, frames=10):
        artifact = Artifact(kind=Kind.TEMPORARY, category='inputs', name=f'{name}.mp4')
        path = self.manager.path(artifact)
        path.parent.mkdir(parents=True, exist_ok=True)
        width, height = size
        frame = np.full((height, width, 3), color, dtype=np.uint8)
        # Asymmetric detail exposes row wrapping, even if total frame bytes match.
        frame[:height // 2, :width // 2] = (240, 240, 240)
        with closing(imageio_ffmpeg.write_frames(
            str(path), size, fps=fps, macro_block_size=1,
        )) as writer:
            writer.send(None)
            for _ in range(frames):
                writer.send(frame.tobytes())
        return artifact

    def decode(self, artifact):
        with closing(imageio_ffmpeg.read_frames(str(self.manager.path(artifact)))) as reader:
            meta = next(reader)
            width, height = meta['size']
            frames = [np.frombuffer(data, np.uint8).reshape(height, width, 3) for data in reader]
        return meta, frames

    def assert_scene(self, frame, color):
        height, width = frame.shape[:2]
        np.testing.assert_allclose(frame[height * 3 // 4, width * 3 // 4], color, atol=12)
        np.testing.assert_allclose(frame[height // 4, width // 4], (240, 240, 240), atol=12)

    def test_mixed_dimensions_preserve_frames_and_scene_boundaries(self):
        colors = [(220, 20, 20), (20, 220, 20), (20, 20, 220)]
        clips = [self.clip(str(i), size, color) for i, (size, color) in enumerate(zip(
            [(64, 96), (60, 92), (64, 96)], colors,
        ))]
        meta, frames = self.decode(self.node.execute(VideoJoiningInput(videos=clips)).video)
        self.assertEqual(meta['size'], (64, 96))
        self.assertEqual(len(frames), 30)
        for index, frame in enumerate(frames):
            self.assert_scene(frame, colors[index // 10])

    def test_equal_byte_counts_with_different_shapes_are_resized(self):
        clips = [self.clip('portrait', (64, 96), (220, 20, 20)),
                 self.clip('landscape', (96, 64), (20, 220, 20))]
        _, frames = self.decode(self.node.execute(VideoJoiningInput(videos=clips)).video)
        self.assertEqual(len(frames), 20)
        # The landscape image fits centrally, without stretching or cropping.
        for frame in frames[10:]:
            np.testing.assert_allclose(frame[0, 32], (0, 0, 0), atol=12)
            np.testing.assert_allclose(frame[60, 48], (20, 220, 20), atol=12)
            np.testing.assert_allclose(frame[35, 16], (240, 240, 240), atol=12)

    def test_mixed_frame_rates_preserve_duration(self):
        clips = [self.clip('slow', (64, 96), (220, 20, 20), fps=10, frames=10),
                 self.clip('fast', (64, 96), (20, 220, 20), fps=20, frames=20)]
        meta, frames = self.decode(self.node.execute(VideoJoiningInput(videos=clips)).video)
        self.assertEqual(meta['fps'], 10)
        self.assertEqual(len(frames), 20)
        self.assertAlmostEqual(meta['duration'], 2.0, places=2)
        for index, frame in enumerate(frames):
            self.assert_scene(frame, (220, 20, 20) if index < 10 else (20, 220, 20))

    def test_repeated_invocations_do_not_reuse_previous_frames_or_dimensions(self):
        first = self.clip('first', (64, 96), (220, 20, 20))
        second = self.clip('second', (80, 120), (20, 220, 20))
        outputs = []
        for clip, size, color in [(first, (64, 96), (220, 20, 20)),
                                  (second, (80, 120), (20, 220, 20)),
                                  (first, (64, 96), (220, 20, 20))]:
            output = self.node.execute(VideoJoiningInput(videos=[clip])).video
            outputs.append(output)
            meta, frames = self.decode(output)
            self.assertEqual(meta['size'], size)
            self.assertEqual(len(frames), 10)
            for frame in frames:
                self.assert_scene(frame, color)
        self.assertEqual(len({output.name for output in outputs}), 3)

    def test_empty_input_is_rejected(self):
        with self.assertRaises(ValueError):
            self.node.execute(VideoJoiningInput(videos=[]))
        self.assertEqual(self.manager.list(Kind.TEMPORARY, 'joined'), [])

    def test_failed_later_clip_does_not_publish_partial_output(self):
        first = self.clip('valid', (64, 96), (220, 20, 20))
        missing = Artifact(kind=Kind.TEMPORARY, category='inputs', name='missing.mp4')
        with self.assertRaises(OSError):
            self.node.execute(VideoJoiningInput(videos=[first, missing]))
        self.assertEqual(self.manager.list(Kind.TEMPORARY, 'joined'), [])
        # A failure must leave the node usable on the next run.
        _, frames = self.decode(self.node.execute(VideoJoiningInput(videos=[first])).video)
        self.assertEqual(len(frames), 10)


class JoinVideosFailureTests(unittest.TestCase):
    def test_bad_frame_and_streams_are_rejected_and_closed(self):
        artifact = Artifact(kind=Kind.TEMPORARY, category='inputs', name='clip.mp4')
        for bad_data in ([b'too short'], []):
            with self.subTest(bad_data=bad_data):
                closed = []

                def reader(name, data, closed=closed):
                    try:
                        yield {'size': (64, 96), 'fps': 10.0}
                        yield from data
                    finally:
                        closed.append(name)

                def writer(*args, closed=closed, **kwargs):
                    try:
                        while True:
                            yield
                    finally:
                        closed.append('writer')

                manager = Mock(spec=ArtifactManager)
                manager.path.return_value = Path(__file__)
                node = JoinVideos(manager, 'joined', Kind.TEMPORARY)
                with (
                    patch.object(imageio_ffmpeg, 'read_frames', side_effect=[
                        reader('probe', []), reader('clip', bad_data),
                    ]),
                    patch.object(imageio_ffmpeg, 'write_frames', side_effect=writer),
                    self.assertRaises(ValueError),
                ):
                    node.execute(VideoJoiningInput(videos=[artifact]))
                self.assertEqual(closed, ['probe', 'clip', 'writer'])
                manager.publish.assert_not_called()

    def test_invalid_frame_rate_is_rejected_and_probe_closed(self):
        artifact = Artifact(kind=Kind.TEMPORARY, category='inputs', name='clip.mp4')
        for fps in (0.0, -1.0, float('nan'), float('inf')):
            with self.subTest(fps=fps):
                closed = []

                def reader(*args, fps=fps, closed=closed):
                    try:
                        yield {'size': (64, 96), 'fps': fps}
                    finally:
                        closed.append(True)

                manager = Mock(spec=ArtifactManager)
                manager.path.return_value = Path(__file__)
                with (
                    patch.object(imageio_ffmpeg, 'read_frames', side_effect=reader),
                    self.assertRaisesRegex(ValueError, 'invalid frame rate'),
                ):
                    JoinVideos(manager, 'joined', Kind.TEMPORARY).execute(
                        VideoJoiningInput(videos=[artifact]),
                    )
                self.assertEqual(closed, [True])
                manager.publish.assert_not_called()


if __name__ == '__main__':
    unittest.main()
