import re
import subprocess
import tempfile
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Final

import imageio_ffmpeg  # type: ignore
import yt_dlp
from langchain_core.tools import BaseTool, tool

from content_automation_pipeline.artifacts.artifact import Artifact, Kind
from content_automation_pipeline.artifacts.artifact_manager import ArtifactManager
from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class ProcessingStrategy(ABC):
    @abstractmethod
    def __call__(self, path: Path, artifact_manager: ArtifactManager, category: str) -> Artifact:
        ...

class Identity(ProcessingStrategy):
    def __call__(self, path: Path, artifact_manager: ArtifactManager, category: str) -> Artifact:
        message = f'using identity processing for {path}'
        _logger.info(message)

        artifact = Artifact(Kind.TEMPORARY, category, path.name)
        artifact_manager.publish(artifact, path, move=True)

        message = f'finished identity processing for {path}'
        _logger.info(message)

        return artifact

class CenterTrim(ProcessingStrategy):
    # Default values that can be overridden by the user
    _DEFAULT_PAD_SECONDS: Final[float] = 5.0

    # Hardcoded values that cannot be overridden by the user
    _DURATION_PATTERN = re.compile(r'Duration: (\d+):(\d+):(\d+\.\d+)')

    def __init__(self, pad_seconds: float = _DEFAULT_PAD_SECONDS) -> None:
        self._pad_seconds = pad_seconds

    def __call__(self, path: Path, artifact_manager: ArtifactManager, category: str) -> Artifact:
        message = f'using center trim processing for {path} with pad_seconds={self._pad_seconds}'
        _logger.info(message)

        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        duration = self._probe_duration(ffmpeg, path)

        center = duration / 2
        start = max(0.0, center - self._pad_seconds)
        end = min(duration, center + self._pad_seconds)

        trimmed_path = path.with_name(f'{uuid.uuid4().hex}.mp4')
        subprocess.run(
            [ffmpeg, '-y', '-i', str(path), '-ss', str(start), '-to', str(end), '-c:v', 'libx264', '-c:a', 'aac', str(trimmed_path)],
            check=True,
            capture_output=True,
        )

        message = f'trimmed {path} to {trimmed_path}'
        _logger.info(message)

        artifact = Artifact(Kind.TEMPORARY, category, path.name)
        artifact_manager.publish(artifact, trimmed_path, move=True)

        message = f'finished center trim processing for {path}'
        _logger.info(message)

        return artifact

    @staticmethod
    def _probe_duration(ffmpeg: str, path: Path) -> float:
        result = subprocess.run([ffmpeg, '-i', str(path)], capture_output=True, text=True, check=False)

        match = CenterTrim._DURATION_PATTERN.search(result.stderr)
        if match is None:
            message = f'could not determine duration of {path}'
            _logger.error(message)
            raise ValueError(message)

        hours, minutes, seconds = match.groups()
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)

class YoutubeDownloader:
    # Default values that can be overridden by the user
    _DEFAULT_STRATEGY: Final[ProcessingStrategy] = Identity()
    _DEFAULT_MAX_RESULTS: Final[int] = 5

    # Hardcoded values that cannot be overridden by the user
    _DOWNLOAD_FORMAT: Final[str] = 'bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/best[ext=mp4]/best'

    def __init__(
        self,
        artifact_manager: ArtifactManager,
        category: str,
        processing_strategy: ProcessingStrategy = _DEFAULT_STRATEGY,
    ) -> None:
        self._artifact_manager = artifact_manager
        self._category = category
        self._processing_strategy = processing_strategy

    def download(self, url: str) -> Artifact:
        with tempfile.TemporaryDirectory() as tmp_dir:
            name = f'{uuid.uuid4().hex}.mp4'
            downloaded_path = Path(tmp_dir) / name

            options: dict[str, Any] = {
                'format': self._DOWNLOAD_FORMAT,
                'merge_output_format': 'mp4',
                'ffmpeg_location': imageio_ffmpeg.get_ffmpeg_exe(),
                'outtmpl': str(downloaded_path),
                'quiet': True,
                'noprogress': True,
            }

            message = f'downloading {url}'
            _logger.info(message)

            with yt_dlp.YoutubeDL(options) as ydl:  # type: ignore
                ydl.download([url])

            message = f'finished downloading {url} to {downloaded_path}'
            _logger.info(message)

            return self._processing_strategy(downloaded_path, self._artifact_manager, self._category)

    @staticmethod
    def search(query: str, max_results: int = _DEFAULT_MAX_RESULTS) -> list[str]:
        message = f'searching for {query!r}'
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

        message = f'finished searching for {query!r}, found {len(urls)} results'
        _logger.info(message)

        return urls

def create_download_tool(youtube_downloader: YoutubeDownloader) -> BaseTool:
    @tool
    def download(url: str) -> str:
        """Download a YouTube video from a URL, save it as an artifact, and return a string summary of the result."""
        artifact = youtube_downloader.download(url)
        return (
            f'Downloaded the video from {url!r} and saved it as artifact {artifact.name!r} '
            f'(kind={artifact.kind}, category={artifact.category!r}).'
        )

    return download

def create_search_tool() -> BaseTool:
    @tool
    def search(query: str) -> str:
        """Search YouTube for videos matching a query, and return a string summary of the results."""
        urls = YoutubeDownloader.search(query)

        if not urls:
            return f'No results found for {query!r}.'

        results = '\n'.join(urls)
        return f'Found {len(urls)} result(s) for {query!r}:\n{results}'

    return search