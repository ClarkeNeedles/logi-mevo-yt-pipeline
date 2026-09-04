"""Command-line entry point and pipeline orchestration."""

import argparse
import os
import shutil
import sys
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

from archiver import ArchiverError, archive_recordings, delete_source_recordings
from concatenator import ConcatenationError, concatenate_recordings
from game_blocks import detect_game_blocks
from scanner import ScannerError, scan_recordings
from youtube_publisher import YouTubePublisherError, build_title, publish_video


def build_parser() -> argparse.ArgumentParser:
	"""Build the command-line argument parser."""
	parser = argparse.ArgumentParser(description="Turn Mevo recordings into game videos.")
	parser.add_argument(
		"--source-dir",
		default=os.getenv("MEVO_SOURCE_DIR", r"E:\DCIM\100_MEVO"),
		help="Directory containing REC_#### source videos.",
	)
	parser.add_argument(
		"--output-dir",
		default=os.getenv("OUTPUT_DIR", "output"),
		help="Directory for concatenated game videos.",
    )
	parser.add_argument(
		"--published-dir",
		default=os.getenv("PUBLISHED_DIR", r"E:\DCIM\100_MEVO\published"),
		help="Directory where successfully processed source recordings are moved when not deleted.",
	)
	parser.add_argument(
		"--confirm-before-publish",
		action="store_true",
		help="Ask for confirmation before the first YouTube upload.",
	)
	parser.add_argument(
		"--dry-run",
		action="store_true",
		help="Show detected games and planned outputs without processing files.",
	)
	parser.add_argument(
		"--delete-source",
		action=argparse.BooleanOptionalAction,
		default=os.getenv("DELETE_SOURCE", "false").strip().lower() in {"1", "true", "yes"},
		help="Delete source recordings after output video is produced instead of archiving them.",
	)
	parser.add_argument(
		"--keep-output",
		action=argparse.BooleanOptionalAction,
		default=os.getenv("KEEP_OUTPUT", "false").strip().lower() in {"1", "true", "yes"},
		help="Keep local output video in output directory after successful YouTube upload (default auto-deletes).",
	)
	return parser


def prompt_team_names() -> tuple[str, str]:
	"""Prompt for the teams that played in the discovered games."""
	while True:
		home_team = input("Home team: ").strip()
		if not home_team:
			print("The home team cannot be blank.")
			continue
		break

	while True:
		away_team = input("Away team: ").strip()
		if not away_team:
			print("The away team cannot be blank.")
			continue
		break

	return home_team, away_team


def prompt_all_team_names(game_count: int) -> list[tuple[str, str]]:
	"""Collect team names for every game before processing begins."""
	if game_count <= 0:
		return []

	print("\nEnter teams for Game 1:")
	first_matchup = prompt_team_names()
	if game_count == 1:
		return [first_matchup]

	while True:
		reuse_teams = input("Use the same team names for all games? [Y/N]: ").strip().lower()
		if reuse_teams in {"y", "yes"}:
			return [first_matchup] * game_count
		if reuse_teams in {"n", "no", ""}:
			break
		print("Please answer Y or N.")

	matchups = [first_matchup]
	for game_number in range(2, game_count + 1):
		print(f"\nEnter teams for Game {game_number}:")
		matchups.append(prompt_team_names())
	return matchups


def verify_output_video(output_path: Path) -> None:
	"""Verify that the generated output video exists and is non-empty."""
	if not output_path.is_file():
		raise ConcatenationError(f"Output video was not created: {output_path}")
	if output_path.stat().st_size == 0:
		raise ConcatenationError(f"Output video is empty (0 bytes): {output_path}")


def prepare_video(block, output_path: Path) -> Path:
	"""Create one game's local output video."""
	is_single_recording = len(block.recordings) == 1
	if is_single_recording:
		output_path.parent.mkdir(parents=True, exist_ok=True)
		if block.recordings[0].path.resolve() == output_path.resolve():
			raise ConcatenationError(
				f"Output path must not replace source recording: {output_path}"
			)
		try:
			shutil.copy2(block.recordings[0].path, output_path)
		except OSError as error:
			raise ConcatenationError(
				f"Could not copy recording to output: {error}"
			) from error
		verify_output_video(output_path)
		return output_path

	result_path = concatenate_recordings(block.recordings, output_path)
	verify_output_video(result_path)
	return result_path


def run_pipeline(arguments: argparse.Namespace) -> int:
	"""Discover games and either preview or concatenate them."""
	try:
		recordings = scan_recordings(arguments.source_dir)
		blocks = detect_game_blocks(recordings)
	except (ScannerError, ValueError) as error:
		print(f"Error: {error}", file=sys.stderr)
		return 1

	if not recordings:
		print(f"No matching recordings found in {arguments.source_dir}")
		return 0

	print(f"Found {len(recordings)} recording(s); detected {len(blocks)} complete game(s).")
	if not blocks:
		print("No complete games found. A game is complete after a short final recording.")
		return 0

	matchups = prompt_all_team_names(len(blocks))
	output_dir = Path(arguments.output_dir)
	output_paths = [
		output_dir / f"{block.game_date.isoformat()}-game-{block.game_number}.mp4"
		for block in blocks
	]
	if arguments.dry_run:
		for block, (home_team, away_team), output_path in zip(blocks, matchups, output_paths):
			filenames = ", ".join(recording.filename for recording in block.recordings)
			title = build_title(home_team, away_team, block.game_date, block.game_number)
			print(f"Game {block.game_number}: {filenames}")
			print(f"  Title: {title}")
			print(f"  Output: {output_path}")
			if arguments.delete_source:
				print(f"  Source action: Delete {filenames} after preparation")
			else:
				print(f"  Source action: Archive to {arguments.published_dir} after preparation")
			if not arguments.keep_output:
				print(f"  Output action: Delete {output_path} after upload")
			else:
				print(f"  Output action: Keep {output_path} after upload")
		print("Dry run complete. No files were processed, uploaded, or deleted.")
		return 0

	if arguments.confirm_before_publish:
		prompt_action = "delete source" if arguments.delete_source else "archive source"
		answer = input(f"Publish ({prompt_action}) these game(s)? [Y/N]: ").strip().lower()
		if answer not in {"y", "yes"}:
			print("Publishing cancelled.")
			return 0

	preparation_future: Future[Path] | None = None
	with ThreadPoolExecutor(max_workers=1, thread_name_prefix="mevo-prep") as executor:
		for index, (block, (home_team, away_team), output_path) in enumerate(
			zip(blocks, matchups, output_paths)
		):
			filenames = ", ".join(recording.filename for recording in block.recordings)
			title = build_title(home_team, away_team, block.game_date, block.game_number)
			is_single_recording = len(block.recordings) == 1
			print(f"\nGame {block.game_number}")
			print(f"  Videos: {filenames}")
			print(f"  Title: {title}")
			print(f"  Output: {output_path}")
			if is_single_recording:
				print("  Preparing: copying the single recording")
			else:
				print("  Preparing: concatenating recordings")
			print("  Preparation progress: 0%")

			try:
				if preparation_future is None:
					prepare_video(block, output_path)
				else:
					print("  Waiting for background preparation to finish...")
					preparation_future.result()
			except (ConcatenationError, ValueError) as error:
				print(f"Error: {error}", file=sys.stderr)
				return 1

			print(f"  Preparation progress: 100%")
			print(f"  Preparation complete: {output_path}")

			if arguments.delete_source:
				try:
					delete_source_recordings(block.recordings)
				except ArchiverError as error:
					print(f"Error: {error}", file=sys.stderr)
					return 1
			else:
				try:
					archive_recordings(block.recordings, arguments.published_dir, output_path.stem)
					print(f"  Archived source recordings in: {arguments.published_dir}")
				except ArchiverError as error:
					print(f"Error: {error}", file=sys.stderr)
					return 1

			preparation_future = None
			if index + 1 < len(blocks):
				next_block = blocks[index + 1]
				next_output_path = output_paths[index + 1]
				preparation_future = executor.submit(
					prepare_video, next_block, next_output_path
				)
				print(
					f"  Started preparing Game {next_block.game_number} in the background "
					"while this upload runs."
				)

			print("  Starting YouTube upload...")
			try:
				def report_upload_progress(percentage: int) -> None:
					print(f"  Upload progress: {percentage}%")

				upload = publish_video(
					output_path,
					home_team,
					away_team,
					block.game_date,
					block.game_number,
					client_secrets_path=os.getenv(
						"YOUTUBE_CLIENT_SECRETS_FILE", "credentials/client_secret.json"
					),
					token_path=os.getenv("YOUTUBE_TOKEN_FILE", "credentials/token.json"),
					progress_callback=report_upload_progress,
				)
			except (YouTubePublisherError, ValueError) as error:
				print(f"Error: {error}", file=sys.stderr)
				return 1

			print(f"  Upload complete: {upload.url}")

			if not arguments.keep_output:
				try:
					output_path.unlink()
					print(f"  Deleted output file: {output_path}")
				except OSError as error:
					print(f"Warning: Could not delete output file {output_path}: {error}", file=sys.stderr)
			else:
				print(f"  Retained output file: {output_path}")

	print("Publishing and processing complete.")
	return 0


def main() -> int:
	"""Run the command-line application."""
	return run_pipeline(build_parser().parse_args())


if __name__ == "__main__":
	raise SystemExit(main())
