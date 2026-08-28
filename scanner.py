"""MicroSD recording discovery and filename validation."""

import json
import re
import subprocess
from pathlib import Path

from models import Recording


RECORDING_PATTERN = re.compile(r"^REC_(\d+)(?:\.[^.]+)?$", re.IGNORECASE)
DEFAULT_VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".m4v"})


class ScannerError(RuntimeError):
	"""Raised when recordings cannot be discovered or measured."""


def scan_recordings(
	source_dir: Path | str,
	*,
	ffprobe_path: str = "ffprobe",
	video_extensions: frozenset[str] = DEFAULT_VIDEO_EXTENSIONS,
) -> list[Recording]:
	"""Find valid Mevo files and return them ordered by recording number."""
	directory = Path(source_dir)
	if not directory.is_dir():
		raise ScannerError(f"Recording directory does not exist: {directory}")

	recordings: list[Recording] = []
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
		duration_seconds = probe_duration(path, ffprobe_path=ffprobe_path)
		recordings.append(Recording(path, number, duration_seconds))

	return sorted(recordings, key=lambda recording: recording.number)


def probe_duration(path: Path | str, *, ffprobe_path: str = "ffprobe") -> float:
	"""Read a video's duration in seconds using ffprobe."""
	command = [
		ffprobe_path,
		"-v",
		"error",
		"-show_entries",
		"format=duration",
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
		duration = float(json.loads(result.stdout)["format"]["duration"])
	except Exception as error:
		raise ScannerError(f"Could not read duration for {path}") from error

	if duration < 0:
		raise ScannerError(f"Invalid negative duration for {path}")
	return duration
