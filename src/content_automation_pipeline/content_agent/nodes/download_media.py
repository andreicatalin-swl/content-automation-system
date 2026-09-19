import json
import os
import shutil
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Final

import imageio_ffmpeg  # type: ignore
import yt_dlp
from pydantic import BaseModel, ConfigDict

from content_automation_pipeline.__about__ import __application__
from content_automation_pipeline.artifacts.artifact import Artifact, Kind
from content_automation_pipeline.artifacts.artifact_manager import ArtifactManager
from content_automation_pipeline.content_agent.models.evaluation import (
    Evaluation,
    Grade,
)
from content_automation_pipeline.content_agent.models.media_files import (
    MediaFile,
    MediaFiles,
)
from content_automation_pipeline.content_agent.models.media_links import MediaLinks
from content_automation_pipeline.content_agent.tools.youtube_downloader import (
    YoutubeDownloader,
)
from content_automation_pipeline.shared.node import Node, Strategy
from content_automation_pipeline.shared.rate_limited_node import RateLimitedNode
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class MediaDownloadInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    media_links: MediaLinks

class MediaDownloadOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    media_files: MediaFiles

# TODO: Implement proper _download_file(...) method
class MediaDownloadStrategy(Strategy[MediaDownloadInput, MediaDownloadOutput]):
    def __init__(
        self,
        artifact_manager: ArtifactManager,
        category: str,
        kind: Kind,
    ) -> None:
        self._artifact_manager = artifact_manager
        self._category = category
        self._kind = kind
        self._downloader = YoutubeDownloader(artifact_manager, category)

    def execute(self, input: MediaDownloadInput) -> MediaDownloadOutput:
        entries = [
            MediaFile(
                audio=self._download_file(entry.audio_link, audio_only=True),
                video=self._download_file(entry.video_link, audio_only=False),
            )
            for entry in input.media_links.entries
        ]

        return MediaDownloadOutput(media_files=MediaFiles(entries=entries))

    def _download_file(self, url: str, audio_only: bool) -> Artifact:
        _WINDOW_SECONDS: Final[float] = 10.0
        # Share of the duration at each end of the video that the heatmap peak may not fall in
        _HEATMAP_MARGIN: Final[float] = 0.05
        _SPONSORBLOCK_ENDPOINT: Final[str] = 'https://sponsor.ajay.app/api/skipSegments'
        _SPONSORBLOCK_TIMEOUT_SECONDS: Final[float] = 10.0
        _HIGHLIGHT_CATEGORY: Final[str] = 'poi_highlight'
        _VIDEO_EXTENSION: Final[str] = 'mp4'
        _AUDIO_EXTENSION: Final[str] = 'mp3'
        _VIDEO_FORMAT: Final[str] = 'bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        _AUDIO_FORMAT: Final[str] = 'bestaudio/best'

        def highlight_start(video_id: str) -> float | None:
            query = urllib.parse.urlencode(
                {
                    'videoID': video_id,
                    'categories': json.dumps([_HIGHLIGHT_CATEGORY]),
                },
            )
            request = urllib.request.Request(
                f'{_SPONSORBLOCK_ENDPOINT}?{query}',
                headers={'User-Agent': __application__},
            )

            try:
                with urllib.request.urlopen(request, timeout=_SPONSORBLOCK_TIMEOUT_SECONDS) as response:
                    segments = json.loads(response.read().decode())
            except urllib.error.HTTPError as error:
                # SponsorBlock answers with 404 when nobody has submitted a segment for the video
                if error.code != 404:
                    message = f'SponsorBlock answered with {error.code} for {video_id}'
                    _logger.warning(message)
                return None
            except (urllib.error.URLError, TimeoutError, ValueError) as error:
                message = f'could not reach SponsorBlock for {video_id}: {error}'
                _logger.warning(message)
                return None

            highlights = [
                segment for segment in segments
                if segment.get('category') == _HIGHLIGHT_CATEGORY and segment.get('segment')
            ]

            if not highlights:
                return None

            # Locked segments win, then the most upvoted one, and the smallest UUID breaks any tie
            best = min(
                highlights,
                key=lambda segment: (
                    -int(segment.get('locked', 0)),
                    -int(segment.get('votes', 0)),
                    str(segment.get('UUID', '')),
                ),
            )

            return float(best['segment'][0])

        def heatmap_start(heatmap: list[dict[str, Any]], duration: float) -> float | None:
            head = duration * _HEATMAP_MARGIN
            tail = duration - head

            # Drop the ends, where the opening and the closing of the video always draw views
            body = [
                point for point in heatmap
                if float(point['start_time']) >= head and float(point['end_time']) <= tail
            ]

            if not body:
                return None

            # The most replayed point wins, and the earliest one breaks any tie
            peak = min(body, key=lambda point: (-float(point['value']), float(point['start_time'])))

            return float(peak['start_time'])

        def start_time(info: dict[str, Any], duration: float) -> float:
            video_id = info.get('id')

            # The moment the SponsorBlock contributors marked as the highlight of the video
            highlight = highlight_start(video_id) if video_id else None
            if highlight is not None:
                message = f'starting at the SponsorBlock highlight of {video_id} at {highlight:.1f}s'
                _logger.info(message)
                return highlight

            # The moment the viewers of the video replayed the most
            peak = heatmap_start(info.get('heatmap') or [], duration)
            if peak is not None:
                message = f'starting at the most replayed moment of {video_id} at {peak:.1f}s'
                _logger.info(message)
                return peak

            message = f'starting at the midpoint of {video_id} at {duration / 2:.1f}s'
            _logger.info(message)
            return duration / 2

        def window(info: dict[str, Any], ydl: Any) -> list[dict[str, float]]:
            duration = info.get('duration')

            # Without a duration there is no way to place the window
            if not duration:
                message = f'could not determine the duration of {info.get("id")}'
                _logger.error(message)
                raise ValueError(message)

            start = start_time(info, float(duration))
            # Keep the whole window inside the video
            start = min(start, max(0.0, duration - _WINDOW_SECONDS))
            end = min(float(duration), start + _WINDOW_SECONDS)

            return [{'start_time': start, 'end_time': end}]

        # yt-dlp refuses to download part of a video unless it finds ffmpeg on the PATH under its plain name
        if shutil.which('ffmpeg') is None:
            executable = Path(imageio_ffmpeg.get_ffmpeg_exe())
            directory = Path(tempfile.gettempdir()) / __application__ / 'ffmpeg'
            directory.mkdir(parents=True, exist_ok=True)
            link = directory / f'ffmpeg{executable.suffix}'

            if not link.exists():
                try:
                    os.link(executable, link)
                except OSError:
                    shutil.copy(executable, link)

            os.environ['PATH'] = f'{directory}{os.pathsep}{os.environ["PATH"]}'

        extension = _AUDIO_EXTENSION if audio_only else _VIDEO_EXTENSION
        options: dict[str, Any] = (
            {
                'format': _AUDIO_FORMAT,
                'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': _AUDIO_EXTENSION}],
            }
            if audio_only
            else {
                'format': _VIDEO_FORMAT,
                'merge_output_format': _VIDEO_EXTENSION,
            }
        )

        # Use a temporary directory to store the window before publishing it as an artifact
        with TemporaryDirectory() as tmp_dir:
            name = uuid.uuid4().hex
            downloaded_path = Path(tmp_dir) / f'{name}.{extension}'

            full_options: dict[str, Any] = {
                'ffmpeg_location': imageio_ffmpeg.get_ffmpeg_exe(),
                'outtmpl': str(Path(tmp_dir) / f'{name}.%(ext)s'),
                'quiet': True,
                'noprogress': True,
                # Only the section this callback returns is downloaded
                'download_ranges': window,
                'force_keyframes_at_cuts': True,
                **options,
            }

            message = f'downloading a {_WINDOW_SECONDS:.0f} second window of {url}'
            _logger.info(message)

            with yt_dlp.YoutubeDL(full_options) as ydl:  # type: ignore
                ydl.download([url])

            message = f'finished downloading {url} to {downloaded_path}'
            _logger.info(message)

            artifact = Artifact(kind=self._kind, category=self._category, name=downloaded_path.name)
            self._artifact_manager.publish(artifact, downloaded_path, move=True)

        return artifact

class DownloadMedia(RateLimitedNode[MediaDownloadInput, MediaDownloadOutput]):
    def __init__(
        self,
        strategy: Strategy[MediaDownloadInput, MediaDownloadOutput],
        max_calls: int = RateLimitedNode._DEFAULT_MAX_CALLS,
    ) -> None:
        super().__init__(strategy, max_calls)

class DownloadedMediaEvaluationInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    # Input for the DownloadMedia node
    media_download_input: MediaDownloadInput
    # Output from the DownloadMedia node
    media_download_output: MediaDownloadOutput
    # Instructions for evaluating output given the input
    evaluation_instructions: str

class DownloadedMediaEvaluationOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    evaluation: Evaluation

# TODO: Implement proper execute(...) method
class DownloadedMediaEvaluationStrategy(Strategy[DownloadedMediaEvaluationInput, DownloadedMediaEvaluationOutput]):
    # Hardcoded values that cannot be overridden by the user
    _NO_FEEDBACK: Final[str] = 'there is no feedback.'

    def execute(self, input: DownloadedMediaEvaluationInput) -> DownloadedMediaEvaluationOutput:
        return DownloadedMediaEvaluationOutput(evaluation=Evaluation(grade=Grade.PASS, feedback=self._NO_FEEDBACK))

class EvaluateDownloadedMedia(Node[DownloadedMediaEvaluationInput, DownloadedMediaEvaluationOutput]):
    def __init__(
        self,
        strategy: Strategy[DownloadedMediaEvaluationInput, DownloadedMediaEvaluationOutput],
    ) -> None:
        super().__init__(strategy)
