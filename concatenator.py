"""FFmpeg-based concatenation of recordings into game videos."""

import subprocess
import tempfile
from collections.abc import Iterable
from pathlib import Path

from config import ffmpeg_executable
from models import Recording


class ConcatenationError(RuntimeError):
	"""Raised when FFmpeg cannot concatenate a recording block."""


def concatenate_recordings(
	recordings: Iterable[Recording],
	output_path: Path | str,
	*,
	ffmpeg_path: str | None = None,
) -> Path:
	"""Join recordings in order and return the generated video path.

	The concat demuxer copies the existing audio and video streams, so the
	source recordings must have compatible stream layouts and codecs.
	"""
	recording_list = list(recordings)
	if not recording_list:
		raise ValueError("At least one recording is required")
	ffmpeg_path = ffmpeg_path or ffmpeg_executable("ffmpeg")

	output = Path(output_path)
	input_paths = [recording.path for recording in recording_list]
	missing_paths = [path for path in input_paths if not path.is_file()]
	if missing_paths:
		raise ConcatenationError(
			"Recording file does not exist: " + ", ".join(str(path) for path in missing_paths)
		)

	resolved_output = output.resolve()
	if any(path.resolve() == resolved_output for path in input_paths):
		raise ConcatenationError("Output path must not replace a source recording")

	output.parent.mkdir(parents=True, exist_ok=True)
	with tempfile.TemporaryDirectory(prefix="mevo-concat-") as temporary_directory:
		file_list = Path(temporary_directory) / "inputs.txt"
		file_list.write_text(
			"".join(f"file '{_escape_concat_path(path)}'\n" for path in input_paths),
			encoding="utf-8",
		)
		command = [
			ffmpeg_path,
			"-hide_banner",
			"-loglevel",
			"error",
			"-nostdin",
			"-y",
			"-f",
			"concat",
			"-safe",
			"0",
			"-i",
			str(file_list),
			"-c",
			"copy",
			str(output),
		]
		try:
			subprocess.run(command, check=True, capture_output=True, text=True)
		except FileNotFoundError as error:
			raise ConcatenationError(
				f"FFmpeg was not found: {ffmpeg_path}"
			) from error
		except subprocess.CalledProcessError as error:
			details = error.stderr.strip() or "no FFmpeg error details available"
			raise ConcatenationError(f"FFmpeg could not concatenate recordings: {details}") from error

	return output


def _escape_concat_path(path: Path) -> str:
	"""Format a path for an FFmpeg concat-demuxer file list."""
	return str(path.resolve()).replace("\\", "/").replace("'", "'\\''")
