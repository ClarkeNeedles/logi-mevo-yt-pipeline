"""YouTube authentication, metadata upload, and video publishing."""

from datetime import date
import os
from pathlib import Path
from dotenv import load_dotenv

from models import UploadResult


load_dotenv()


YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
YOUTUBE_API_SERVICE = "youtube"
YOUTUBE_API_VERSION = "v3"


class YouTubePublisherError(RuntimeError):
	"""Raised when YouTube authentication or upload fails."""


def authenticate(
	client_secrets_path: Path | str = Path("credentials/client_secret.json"),
	token_path: Path | str = Path("credentials/token.json"),
):
	"""Authenticate the local user and return YouTube API credentials."""
	try:
		from google.auth.transport.requests import Request
		from google.oauth2.credentials import Credentials
		from google_auth_oauthlib.flow import InstalledAppFlow
	except ImportError as error:
		raise YouTubePublisherError(
			"YouTube dependencies are not installed. Run: pip install -r requirements.txt"
		) from error

	token = Path(token_path)
	client_secrets = Path(client_secrets_path)
	credentials = None
	if token.is_file():
		credentials = Credentials.from_authorized_user_file(str(token), [YOUTUBE_UPLOAD_SCOPE])

	if credentials is None or not credentials.valid:
		if credentials is not None and credentials.expired and credentials.refresh_token:
			credentials.refresh(Request())
		else:
			if not client_secrets.is_file():
				raise YouTubePublisherError(
					f"OAuth client secrets file does not exist: {client_secrets}"
				)
			flow = InstalledAppFlow.from_client_secrets_file(
				str(client_secrets), [YOUTUBE_UPLOAD_SCOPE]
			)
			credentials = flow.run_local_server(port=0)

		token.parent.mkdir(parents=True, exist_ok=True)
		token.write_text(credentials.to_json(), encoding="utf-8")

	return credentials


def build_title(home_team: str, away_team: str, game_date: date, game_number: int) -> str:
	"""Build the standard title for a published game video."""
	if not home_team.strip() or not away_team.strip():
		raise ValueError("Both team names are required")
	if game_number <= 0:
		raise ValueError("game_number must be greater than zero")
	return f"{home_team.strip()} vs {away_team.strip()} - {game_date.isoformat()} - Game {game_number}"


def publish_video(
	video_path: Path | str,
	home_team: str,
	away_team: str,
	game_date: date,
	game_number: int,
	*,
	client_secrets_path: Path | str = Path("credentials/client_secret.json"),
	token_path: Path | str = Path("credentials/token.json"),
	description: str = "",
	category_id: str | None = None,
	privacy_status: str | None = None,
) -> UploadResult:
	"""Upload a game video publicly and return its YouTube URL.

	No custom thumbnail is supplied, allowing YouTube to select a video frame.
	"""
	video = Path(video_path)
	if not video.is_file():
		raise YouTubePublisherError(f"Video file does not exist: {video}")
	category_id = category_id or os.getenv("YOUTUBE_CATEGORY_ID", "17")
	privacy_status = privacy_status or os.getenv("YOUTUBE_PRIVACY_STATUS", "public")
	if privacy_status not in {"public", "private", "unlisted"}:
		raise ValueError("privacy_status must be public, private, or unlisted")

	try:
		from googleapiclient.discovery import build
		from googleapiclient.http import MediaFileUpload
		from googleapiclient.errors import HttpError
	except ImportError as error:
		raise YouTubePublisherError(
			"YouTube dependencies are not installed. Run: pip install -r requirements.txt"
		) from error

	credentials = authenticate(client_secrets_path, token_path)
	youtube = build(YOUTUBE_API_SERVICE, YOUTUBE_API_VERSION, credentials=credentials)
	body = {
		"snippet": {
			"title": build_title(home_team, away_team, game_date, game_number),
			"description": description,
			"categoryId": category_id,
		},
		"status": {"privacyStatus": privacy_status},
	}
	media = MediaFileUpload(str(video), mimetype="video/*", resumable=True)
	try:
		request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
		response = None
		while response is None:
			_, response = request.next_chunk()
	except HttpError as error:
		raise YouTubePublisherError(f"YouTube upload failed: {error}") from error
	finally:
		if hasattr(media, "_fd") and media._fd is not None:
			try:
				media._fd.close()
			except Exception:
				pass

	video_id = response.get("id") if response else None
	if not video_id:
		raise YouTubePublisherError("YouTube upload returned no video ID")

	upload_status = response.get("status", {}).get("uploadStatus")
	if upload_status in {"rejected", "failed"}:
		rejection_reason = response.get("status", {}).get("rejectionReason", "unknown")
		raise YouTubePublisherError(
			f"YouTube upload was {upload_status}: {rejection_reason}"
		)

	return UploadResult(video_id, f"https://www.youtube.com/watch?v={video_id}")
