# pyright: reportMissingTypeStubs=false

from pathlib import Path
from typing import Final, Protocol, TypedDict, cast

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import (
    build,  # pyright: ignore[reportUnknownVariableType]
)
from googleapiclient.http import MediaFileUpload
from pydantic import BaseModel, ConfigDict

from content_automation_pipeline.utilities.logger import create_logger

_logger = create_logger(__name__)

class _ChannelSnippet(TypedDict):
    title: str
    customUrl: str

class _ChannelItem(TypedDict):
    id: str
    snippet: _ChannelSnippet

class _ChannelListResponse(TypedDict):
    items: list[_ChannelItem]

class _UploadResponse(TypedDict):
    id: str

class _ChannelListRequest(Protocol):
    def execute(self) -> object: ...

class _ChannelsResource(Protocol):
    def list(self, *, part: str, mine: bool) -> _ChannelListRequest: ...

class _UploadRequest(Protocol):
    def next_chunk(self) -> tuple[object | None, object | None]: ...

class _VideosResource(Protocol):
    def insert(
        self,
        *,
        part: str,
        body: dict[str, object],
        media_body: object,
        notifySubscribers: bool,
    ) -> _UploadRequest: ...

class _YoutubeService(Protocol):
    def channels(self) -> _ChannelsResource: ...

    def videos(self) -> _VideosResource: ...

class YoutubeChannel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)

    id: str
    title: str
    custom_url: str | None = None

# TODO: Implement proper YoutubeUploader class
class YoutubeUploader:
    _SCOPES: Final[tuple[str, ...]] = (
        'https://www.googleapis.com/auth/youtube.readonly',
        'https://www.googleapis.com/auth/youtube.upload',
    )

    def __init__(self, client_secrets_path: Path, token_path: Path) -> None:
        self._client_secrets_path = client_secrets_path
        self._token_path = token_path

    def channel(self) -> YoutubeChannel:
        response = cast(
            _ChannelListResponse,
            self._service().channels().list(part='id,snippet', mine=True).execute(),
        )
        item = response['items'][0]
        snippet = item['snippet']

        return YoutubeChannel(
            id=item['id'],
            title=snippet['title'],
            custom_url=snippet.get('customUrl'),
        )

    def upload(
        self,
        video_path: Path,
        body: dict[str, object],
        notify_subscribers: bool,
    ) -> str:
        media = MediaFileUpload(
            str(video_path),
            mimetype='video/*',
            resumable=True,
        )
        request = self._service().videos().insert(
            part='snippet,status',
            body=body,
            media_body=media,
            notifySubscribers=notify_subscribers,
        )

        response: _UploadResponse | None = None
        while response is None:
            _, raw_response = request.next_chunk()
            if raw_response is not None:
                response = cast(_UploadResponse, raw_response)

        return response['id']

    def _service(self) -> _YoutubeService:
        return cast(
            _YoutubeService,
            build(
                'youtube',
                'v3',
                credentials=self._credentials(),
                cache_discovery=False,
            ),
        )

    def _credentials(self) -> Credentials:
        credentials: Credentials | None = None
        save_credentials = False

        if self._token_path.is_file():
            credentials = Credentials.from_authorized_user_file(  # pyright: ignore[reportUnknownMemberType]
                str(self._token_path),
                list(self._SCOPES),
            )

        if credentials is not None and credentials.expired and credentials.refresh_token:  # pyright: ignore[reportUnknownMemberType]
            credentials.refresh(Request())  # pyright: ignore[reportUnknownMemberType]
            save_credentials = True
        elif credentials is None or not credentials.valid:
            flow = InstalledAppFlow.from_client_secrets_file(  # pyright: ignore[reportUnknownMemberType]
                str(self._client_secrets_path),
                list(self._SCOPES),
            )
            credentials = cast(
                Credentials,
                flow.run_local_server(port=0),  # pyright: ignore[reportUnknownMemberType]
            )
            save_credentials = True

        assert credentials is not None
        if save_credentials:
            self._token_path.parent.mkdir(parents=True, exist_ok=True)
            _ = self._token_path.write_text(
                credentials.to_json(),  # pyright: ignore[reportUnknownMemberType]
                encoding='utf-8',
            )

        return credentials
