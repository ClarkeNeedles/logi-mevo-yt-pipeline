"""Application settings and environment configuration."""

import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()

DEFAULT_FFMPEG_BIN_DIR = r"C:\ffmpeg\bin"


def ffmpeg_executable(name: str) -> str:
	"""Return the configured path to an FFmpeg executable."""
	bin_dir = os.getenv("FFMPEG_BIN_DIR", DEFAULT_FFMPEG_BIN_DIR)
	return str(Path(bin_dir) / f"{name}.exe")
