"""MicroSD recording discovery and filename validation."""

import json
import re
import subprocess
from datetime import date, datetime
from pathlib import Path

from config import ffmpeg_executable
from models import Recording


RECORDING_PATTERN = re.compile(r"^REC_(\d+)(?:\.[^.]+)?$", re.IGNORECASE)
DEFAULT_VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".m4v"})


class ScannerError(RuntimeError):
	"""Raised when recordings cannot be discovered or measured."""


def scan_recordings(
	source_dir: Path | str,
	*,
	ffprobe_path: str | None = None,
	video_extensions: frozenset[str] = DEFAULT_VIDEO_EXTENSIONS,
) -> list[Recording]:
	"""Find valid Mevo files and return them ordered by recording number."""
	directory = Path(source_dir)
	if not directory.is_dir():
		raise ScannerError(f"Recording directory does not exist: {directory}")

	recordings: list[Recording] = []
	ffprobe_path = ffprobe_path or ffmpeg_executable("ffprobe")
	seen_numbers: set[int] = set()
	for path in directory.iterdir():
		if not path.is_file() or path.suffix.lower() not in video_extensions:
			continue

		match = RECORDING_PATTERN.fullmatch(path.name)
		if match is None:
			continue

		number = int(match.group(1))
		if number in seen_numbers:
			raise ScannerError(f"Duplicate recording number {number}: {path.name}")
		seen_numbers.add(number)
		duration_seconds, recorded_date = probe_metadata(path, ffprobe_path=ffprobe_path)
		recordings.append(Recording(path, number, duration_seconds, recorded_date))

	return sorted(recordings, key=lambda recording: recording.number)

def probe_metadata(path: Path | str, *, ffprobe_path: str | None = None) -> tuple[float, date]:
	"""Read a video's duration and recording date from FFmpeg metadata."""
	ffprobe_path = ffprobe_path or ffmpeg_executable("ffprobe")
	command = [
		ffprobe_path,
		"-v",
		"error",
		"-show_entries",
		"format=duration:format_tags=creation_time,com.apple.quicktime.creationdate",
		"-of",
		"json",
		str(path),
	]
	try:
		result = subprocess.run(
			command,
			check=True,
			capture_output=True,
			text=True,
		)
		metadata = json.loads(result.stdout)["format"]
		duration = float(metadata["duration"])
		tags = metadata.get("tags", {})
		creation_time = tags.get("creation_time") or tags.get("com.apple.quicktime.creationdate")
		if not creation_time:
			raise ValueError("recording date metadata is missing")
		recorded_date = _parse_recorded_date(creation_time)
	except Exception as error:
		raise ScannerError(f"Could not read duration for {path}") from error

	if duration < 0:
		raise ScannerError(f"Invalid negative duration for {path}")
	return duration, recorded_date


def _parse_recorded_date(value: str) -> date:
	"""Parse an FFmpeg ISO 8601 creation timestamp into a calendar date."""
	return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
