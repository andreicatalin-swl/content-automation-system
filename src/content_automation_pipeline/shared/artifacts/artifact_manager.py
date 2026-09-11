import shutil
from pathlib import Path

from filelock import FileLock

from content_automation_pipeline.shared.artifacts.artifact import Artifact, Kind
from content_automation_pipeline.shared.utilities.logger import create_logger

_logger = create_logger(__name__)

class ArtifactManager:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def path(self, artifact: Artifact) -> Path:
        # Construct the path for the artifact
        path = (
            self._root
            / artifact.kind.value
            / artifact.category
            / artifact.name
        ).resolve()

        # Check if the constructed path is a subpath of the root directory
        try:
            path.relative_to(self._root)
        except ValueError:
            message = f'path {path} is not a subpath of {self._root}'
            _logger.error(message)
            raise ValueError(message) from None

        return path

    def exists(self, artifact: Artifact) -> bool:
        destination = self.path(artifact)
        # Acquire the lock on the destination path to ensure thread safety
        with self._lock(destination):
            return destination.exists()

    def publish(self, artifact: Artifact, source: Path, move: bool = False) -> None:
        source = source.resolve()
        destination = self.path(artifact)

        # Check if the source and destination paths are the same
        if source == destination:
            message = f'source and destination are the same path: {source}'
            _logger.error(message)
            raise ValueError(message)

        # Copy to a same-directory temporary file, then atomically rename it into place
        tmp_destination = destination.parent / f'.{destination.name}.tmp'

        # Use fixed global ordering to avoid deadlocks when acquiring the locks on all three paths
        first, second, third = sorted((source, destination, tmp_destination), key=str)
        # Acquire the locks on all three paths to ensure thread safety, held until tmp_destination no longer exists
        with self._lock(first), self._lock(second), self._lock(third):
            if not source.is_file():
                message = f'source {source} is not a file'
                _logger.error(message)
                raise FileNotFoundError(message)

            if destination.exists():
                message = f'destination {destination} already exists'
                _logger.error(message)
                raise FileExistsError(message)

            try:
                shutil.copy(source, tmp_destination)
                tmp_destination.replace(destination)
            except OSError as error:
                message = f'failed to publish {artifact} to {destination}: {error}'
                _logger.error(message)
                tmp_destination.unlink(missing_ok=True)
                raise OSError(message) from error

            if move:
                try:
                    source.unlink()
                except OSError as error:
                    message = f'failed to remove source {source} after publishing to {destination}: {error}'
                    _logger.error(message)
                    raise OSError(message) from error

    def delete(self, artifact: Artifact, missing_ok: bool = False) -> None:
        destination = self.path(artifact)
        # Acquire the lock on the destination path to ensure thread safety
        with self._lock(destination):
            try:
                destination.unlink()
            except FileNotFoundError:
                if missing_ok:
                    return
                message = f'artifact {artifact} does not exist'
                _logger.error(message)
                raise FileNotFoundError(message) from None

    def list(self, kind: Kind, category: str) -> list[Artifact]:
        directory = (self._root / kind.value / category).resolve()
        if not directory.is_dir():
            return []

        names = sorted(path.name for path in directory.iterdir() if path.is_file() and not path.name.startswith('.'))
        return [Artifact(kind, category, name) for name in names]

    def _lock(self, path: Path) -> FileLock:
        path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = path.parent / f'.{path.name}.lock'
        # Return a FileLock object (mutex) for the given lock path
        return FileLock(str(lock_path))
