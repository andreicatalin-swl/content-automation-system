import tempfile
import uuid
from pathlib import Path
from typing import Any, Final

import imageio_ffmpeg  # type: ignore
import yt_dlp

from content_automation_pipeline.artifacts.artifact import Artifact, Kind
from content_automation_pipeline.artifacts.artifact_manager import ArtifactManager
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class YoutubeDownloader:
    # Default values that can be overridden by the user
    _DEFAULT_MAX_RESULTS: Final[int] = 5

    # Hardcoded values that cannot be overridden by the user
    _VIDEO_EXTENSION: Final[str] = 'mp4'
    _AUDIO_EXTENSION: Final[str] = 'mp3'
    _VIDEO_FORMAT: Final[str] = 'bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/best[ext=mp4]/best'
    _AUDIO_FORMAT: Final[str] = 'bestaudio/best'

    def __init__(
        self,
        artifact_manager: ArtifactManager,
        category: str,
    ) -> None:
        self._artifact_manager = artifact_manager
        self._category = category

    def download_mp4(self, url: str) -> Artifact:
        options: dict[str, Any] = {
            'format': self._VIDEO_FORMAT,
            'merge_output_format': self._VIDEO_EXTENSION,
        }
        return self._download(url, self._VIDEO_EXTENSION, options)

    def download_mp3(self, url: str) -> Artifact:
        options: dict[str, Any] = {
            'format': self._AUDIO_FORMAT,
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': self._AUDIO_EXTENSION}],
        }
        return self._download(url, self._AUDIO_EXTENSION, options)

    def _download(self, url: str, extension: str, options: dict[str, Any]) -> Artifact:
        with tempfile.TemporaryDirectory() as tmp_dir:
            name = uuid.uuid4().hex
            downloaded_path = Path(tmp_dir) / f'{name}.{extension}'

            full_options: dict[str, Any] = {
                'ffmpeg_location': imageio_ffmpeg.get_ffmpeg_exe(),
                'outtmpl': str(Path(tmp_dir) / f'{name}.%(ext)s'),
                'quiet': True,
                'noprogress': True,
                **options,
            }

            message = f'downloading {url}'
            _logger.info(message)

            with yt_dlp.YoutubeDL(full_options) as ydl:  # type: ignore
                ydl.download([url])

            message = f'finished downloading {url} to {downloaded_path}'
            _logger.info(message)

            artifact = Artifact(kind=Kind.TEMPORARY, category=self._category, name=downloaded_path.name)
            self._artifact_manager.publish(artifact, downloaded_path, move=True)

        return artifact

    @staticmethod
    def search(query: str, max_results: int = _DEFAULT_MAX_RESULTS) -> list[str]:
        message = f'searching for {query}'
        _logger.info(message)

        options: dict[str, Any] = {
            'quiet': True,
            'noprogress': True,
            'extract_flat': True,
        }

        with yt_dlp.YoutubeDL(options) as ydl:  # type: ignore
            info = ydl.extract_info(f'ytsearch{max_results}:{query}', download=False)

        entries = info.get('entries', []) if info else []
        urls = [url for entry in entries if isinstance(url := entry.get('url'), str)]

        message = f'finished searching for {query}, found {len(urls)} results'
        _logger.info(message)

        return urls
