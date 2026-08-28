"""Command-line entry point and pipeline orchestration."""

import argparse
import os
import sys
from pathlib import Path

from archiver import ArchiverError, archive_recordings
from concatenator import ConcatenationError, concatenate_recordings
from game_blocks import SHORT_THRESHOLD_SECONDS, detect_game_blocks
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
		"--short-threshold-minutes",
		type=float,
		default=SHORT_THRESHOLD_SECONDS / 60,
		help="Maximum duration considered a short final recording.",
	)
	parser.add_argument(
		"--ffprobe-path",
		default="ffprobe",
		help="ffprobe executable or full path.",
	)
	parser.add_argument(
		"--ffmpeg-path",
		default="ffmpeg",
		help="ffmpeg executable or full path.",
	)
	parser.add_argument(
		"--published-dir",
		default=os.getenv("PUBLISHED_DIR", r"E:\DCIM\100_MEVO\published"),
		help="Directory where successfully uploaded source recordings are moved.",
	)
	parser.add_argument(
		"--confirm-before-publish",
		action="store_true",
		help="Ask for confirmation before the first YouTube upload.",
	)
	parser.add_argument(
		"--dry-run",
		action="store_true",
		help="Show detected games and planned outputs without concatenating files.",
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


def run_pipeline(arguments: argparse.Namespace) -> int:
	"""Discover games and either preview or concatenate them."""
	try:
		recordings = scan_recordings(
			arguments.source_dir,
			ffprobe_path=arguments.ffprobe_path,
		)
		blocks = detect_game_blocks(
			recordings,
			short_threshold_seconds=arguments.short_threshold_minutes * 60,
		)
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

	home_team, away_team = prompt_team_names()
	output_dir = Path(arguments.output_dir)
	for block in blocks:
		output_path = output_dir / f"{block.game_date.isoformat()}-game-{block.game_number}.mp4"
		filenames = ", ".join(recording.filename for recording in block.recordings)
		title = build_title(home_team, away_team, block.game_date, block.game_number)
		print(f"Game {block.game_number}: {filenames}")
		print(f"  Title: {title}")
		print(f"  Output: {output_path}")
		if arguments.dry_run:
			continue

		if arguments.confirm_before_publish and block.game_number == blocks[0].game_number:
			answer = input("Publish and archive these game(s)? [y/N]: ").strip().lower()
			if answer not in {"y", "yes"}:
				print("Publishing cancelled.")
				return 0

		try:
			concatenate_recordings(
				block.recordings,
				output_path,
				ffmpeg_path=arguments.ffmpeg_path,
			)
		except (ConcatenationError, ValueError) as error:
			print(f"Error: {error}", file=sys.stderr)
			return 1

		print(f"  Created: {output_path}")
		try:
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
			)
			archive_recordings(block.recordings, arguments.published_dir)
		except (YouTubePublisherError, ArchiverError, ValueError) as error:
			print(f"Error: {error}", file=sys.stderr)
			return 1

		print(f"  Published: {upload.url}")
		print(f"  Archived source recordings in: {arguments.published_dir}")

	if arguments.dry_run:
		print("Dry run complete. No files were concatenated or moved.")
	else:
		print("Publishing and archiving complete.")
	return 0


def main() -> int:
	"""Run the command-line application."""
	return run_pipeline(build_parser().parse_args())


if __name__ == "__main__":
	raise SystemExit(main())
