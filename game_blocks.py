"""Detection of complete game blocks from ordered recordings."""

from collections.abc import Iterable

from models import GameBlock, Recording


SHORT_THRESHOLD_SECONDS = 59 * 60


def detect_game_blocks(
	recordings: Iterable[Recording],
	*,
	short_threshold_seconds: float = SHORT_THRESHOLD_SECONDS,
	starting_game_number: int = 1,
) -> list[GameBlock]:
	"""Return complete game blocks terminated by a short recording.

	The input is expected to already be ordered by recording number. A trailing
	group without a short recording is considered incomplete and is not returned.
	A recording exactly at the threshold is treated as a full-length recording.
	"""
	if short_threshold_seconds <= 0:
		raise ValueError("short_threshold_seconds must be greater than zero")
	if starting_game_number <= 0:
		raise ValueError("starting_game_number must be greater than zero")

	complete_blocks: list[GameBlock] = []
	current_recordings: list[Recording] = []
	next_game_number = starting_game_number

	for recording in recordings:
		current_recordings.append(recording)
		if recording.duration_seconds < short_threshold_seconds:
			complete_blocks.append(
				GameBlock(tuple(current_recordings), next_game_number)
			)
			next_game_number += 1
			current_recordings = []

	return complete_blocks
