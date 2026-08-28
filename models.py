"""Shared data models for recordings, game blocks, and uploads."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Recording:
	"""A discovered Mevo recording and its measured duration."""

	path: Path
	number: int
	duration_seconds: float

	@property
	def filename(self) -> str:
		"""Return the source filename."""
		return self.path.name

	@property
	def duration_minutes(self) -> float:
		"""Return the duration in minutes."""
		return self.duration_seconds / 60


@dataclass(frozen=True)
class GameBlock:
	"""An ordered group of recordings that make up one game."""

	recordings: tuple[Recording, ...]
	game_number: int


@dataclass(frozen=True)
class UploadResult:
	"""The result of a successful YouTube upload."""

	video_id: str
	url: str
