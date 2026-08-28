"""Archiving of source recordings after successful publication."""

import shutil
from collections.abc import Iterable
from pathlib import Path

from models import Recording


class ArchiverError(RuntimeError):
	"""Raised when source recordings cannot be archived safely."""


def archive_recordings(
	recordings: Iterable[Recording],
	published_dir: Path | str,
) -> list[Path]:
	"""Move processed recordings into ``published_dir`` and return destinations.

	Call this only after the corresponding concatenation and YouTube upload have
	succeeded. All source and destination paths are checked before any move.
	"""
	recording_list = list(recordings)
	if not recording_list:
		return []

	destination_dir = Path(published_dir)
	sources = [recording.path for recording in recording_list]
	if len({path.resolve() for path in sources}) != len(sources):
		raise ArchiverError("The same source recording was supplied more than once")

	missing_sources = [path for path in sources if not path.is_file()]
	if missing_sources:
		raise ArchiverError(
			"Source recording does not exist: "
			+ ", ".join(str(path) for path in missing_sources)
		)

	destinations = [destination_dir / path.name for path in sources]
	if len({path.name.casefold() for path in destinations}) != len(destinations):
		raise ArchiverError("Source recordings contain duplicate destination filenames")

	existing_destinations = [path for path in destinations if path.exists()]
	if existing_destinations:
		raise ArchiverError(
		"Archive destination already exists: "
		+ ", ".join(str(path) for path in existing_destinations)
	)

	destination_dir.mkdir(parents=True, exist_ok=True)
	moved: list[tuple[Path, Path]] = []
	try:
		for source, destination in zip(sources, destinations):
			shutil.move(str(source), str(destination))
			moved.append((source, destination))
	except (OSError, shutil.Error) as error:
		for source, destination in reversed(moved):
			try:
				shutil.move(str(destination), str(source))
			except OSError:
				pass
		raise ArchiverError(f"Could not archive recordings: {error}") from error

	return destinations
