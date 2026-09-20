import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Final

import imageio_ffmpeg  # type: ignore
import yt_dlp
from yt_dlp.utils import DownloadError  # type: ignore

from content_automation_pipeline.__about__ import __application__
from content_automation_pipeline.artifacts.artifact import Artifact, Kind
from content_automation_pipeline.artifacts.artifact_manager import ArtifactManager
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

# TODO: Implement proper YoutubeDownloader class
class YoutubeDownloader:
    # Default values that can be overridden by the user
    _DEFAULT_MAX_RESULTS: Final[int] = 5
    _DEFAULT_MAX_ATTEMPTS: Final[int] = 5

    # Hardcoded values that cannot be overridden by the user
    _VIDEO_EXTENSION: Final[str] = 'mp4'
    _AUDIO_EXTENSION: Final[str] = 'mp3'
    _VIDEO_FORMAT: Final[str] = 'bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/best[ext=mp4]/best'
    _AUDIO_FORMAT: Final[str] = 'bestaudio/best'
    _PAUSE_SECONDS: Final[float] = 3.0
    _BACKOFF_SECONDS: Final[float] = 8.0
    _SOCKET_TIMEOUT_SECONDS: Final[float] = 30.0
    _RETRIES: Final[int] = 10

    def __init__(
        self,
        artifact_manager: ArtifactManager,
        category: str,
        kind: Kind = Kind.TEMPORARY,
        max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
    ) -> None:
        self._artifact_manager = artifact_manager
        self._category = category
        self._kind = kind
        self._max_attempts = max_attempts
        self._downloads = 0

    def download_mp4(self, url: str, start_timestamp: float, duration: float) -> Artifact:
        options: dict[str, Any] = {
            'format': self._VIDEO_FORMAT,
            'merge_output_format': self._VIDEO_EXTENSION,
        }
        return self._download(url, self._VIDEO_EXTENSION, start_timestamp, duration, options)

    def download_mp3(self, url: str, start_timestamp: float, duration: float) -> Artifact:
        options: dict[str, Any] = {
            'format': self._AUDIO_FORMAT,
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': self._AUDIO_EXTENSION}],
        }
        return self._download(url, self._AUDIO_EXTENSION, start_timestamp, duration, options)

    def _download(
        self,
        url: str,
        extension: str,
        start_timestamp: float,
        duration: float,
        options: dict[str, Any],
    ) -> Artifact:
        self._put_ffmpeg_on_path()

        def ranges(_info: dict[str, Any], _ydl: Any) -> list[dict[str, float]]:
            return [{'start_time': start_timestamp, 'end_time': start_timestamp + duration}]

        # Leave YouTube alone for a moment before asking it for another file
        if self._downloads:
            time.sleep(self._PAUSE_SECONDS)

        self._downloads += 1

        message = f'downloading {duration:.0f} seconds of {url} from {start_timestamp:.1f}s'
        _logger.info(message)

        for attempt in range(1, self._max_attempts + 1):
            # Give every attempt its own directory so a half written file cannot be picked up
            with tempfile.TemporaryDirectory() as tmp_dir:
                name = uuid.uuid4().hex
                downloaded_path = Path(tmp_dir) / f'{name}.{extension}'

                full_options: dict[str, Any] = {
                    'ffmpeg_location': imageio_ffmpeg.get_ffmpeg_exe(),
                    'outtmpl': str(Path(tmp_dir) / f'{name}.%(ext)s'),
                    'quiet': True,
                    'noprogress': True,
                    # A link to anything other than a single video must not turn into a bulk download
                    'noplaylist': True,
                    'playlist_items': '1',
                    'socket_timeout': self._SOCKET_TIMEOUT_SECONDS,
                    'retries': self._RETRIES,
                    'fragment_retries': self._RETRIES,
                    'extractor_retries': self._RETRIES,
                    'file_access_retries': self._RETRIES,
                    # Only the section this callback returns is downloaded
                    'download_ranges': ranges,
                    # Without this the section is copied, and the cut lands on the nearest packet
                    # boundary instead of the timestamp that was asked for
                    'force_keyframes_at_cuts': True,
                    **self._runtime_options(),
                    **options,
                }

                failure = self._attempt(url, full_options, downloaded_path)

                if failure is None:
                    message = f'finished downloading {url} to {downloaded_path}'
                    _logger.info(message)

                    artifact = Artifact(kind=self._kind, category=self._category, name=downloaded_path.name)
                    self._artifact_manager.publish(artifact, downloaded_path, move=True)

                    return artifact

                message = f'attempt {attempt}/{self._max_attempts} failed for {url}: {failure}'
                _logger.warning(message)

            if attempt < self._max_attempts:
                time.sleep(self._BACKOFF_SECONDS * attempt)

        message = f'reached the maximum of {self._max_attempts} attempt(s) to download {url}'
        _logger.error(message)
        raise RuntimeError(message)

    @staticmethod
    def _attempt(url: str, full_options: dict[str, Any], downloaded_path: Path) -> str | None:
        try:
            with yt_dlp.YoutubeDL(full_options) as ydl:  # type: ignore
                ydl.download([url])
        except (DownloadError, OSError) as error:
            return str(error)

        if not downloaded_path.is_file():
            return f'{downloaded_path.name} was never written'

        if not downloaded_path.stat().st_size:
            return f'{downloaded_path.name} is empty'

        return None

    @staticmethod
    def _runtime_options() -> dict[str, Any]:
        # yt-dlp only enables deno on its own, so hand it the runtime that is actually installed
        if shutil.which('node') is None:
            return {}

        return {'js_runtimes': {'node': {}}}

    @staticmethod
    def _put_ffmpeg_on_path() -> None:
        if shutil.which('ffmpeg') is not None:
            return

        # yt-dlp only recognises the binary under its plain name, so link it under that name
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
        # Channels and playlists also come back from a search, and neither is a single video
        urls = [
            url for entry in entries
            if entry.get('ie_key') == 'Youtube' and isinstance(url := entry.get('url'), str)
        ]

        message = f'finished searching for {query}, found {len(urls)} results'
        _logger.info(message)

        return urls
