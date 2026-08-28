# Logi Mevo to YouTube Pipeline

Turn Logi Mevo recordings from a MicroSD card into public YouTube videos for the team.

## Planned workflow

The pipeline will run on Windows and use the card mounted as `E:`:

1. Scan `E:\DCIM\100_MEVO` for files named `REC_0001`, `REC_0002`, and so on. Only completed video files matching the expected naming pattern will be considered.
2. Sort the recordings by their numeric recording number, not by filename text or filesystem date.
3. Treat recordings as game blocks. A block contains one or more recordings of about one hour and ends at the first recording shorter than one hour. For example:

	```text
	REC_0001  1 hour
	REC_0002  1 hour
	REC_0003  34 minutes  <- Game 1 ends here
	REC_0004  1 hour
	REC_0005  1 hour
	REC_0006  41 minutes  <- Game 2 ends here
	```

4. Do not process an incomplete block. If the final recording is still about one hour, wait until a shorter recording appears.
5. Concatenate each complete block in order, without re-encoding when the input files are compatible.
6. Create an output filename containing the date and game number, for example `2026-08-28-game-1.mp4` and `2026-08-28-game-2.mp4`.
7. Create a YouTube title containing:
	- the two team names;
	- the game date;
	- `Game 1`, `Game 2`, etc.
8. Upload the finished video to the configured YouTube channel with visibility set to `public`. YouTube will select a frame from the video automatically because no custom thumbnail is supplied.
9. Move every source recording used successfully for the upload into `E:\DCIM\100_MEVO\published`. This keeps old `REC_####` files out of the next run, so a new card recording can start again at `REC_0001`.

Source recordings must be moved only after concatenation and YouTube upload succeed. If a step fails, leave the source files in place so the run can be retried.

## Proposed project steps

We will build this incrementally:

1. **Configuration:** add settings for the card path, output path, short-file threshold, team names, date, and game numbering.
2. **Discovery:** scan and validate `REC_####` files, sort them numerically, and print a dry-run summary.
3. **Block detection:** identify complete game blocks by their short final recording and stop safely on incomplete input.
4. **Concatenation:** use FFmpeg to join each block and write date/game output files.
5. **YouTube authentication:** configure the YouTube Data API with OAuth 2.0 and store credentials locally, never in source control.
6. **Upload:** publish the video, title, description, and metadata; support a dry-run mode before public uploads.
7. **Archiving:** move only successfully processed source recordings into `published` and write a run log.
8. **Recovery and tests:** test repeated runs, missing files, duplicate numbering, failed uploads, and a card containing one or two games.

## Project structure

```text
main.py                 # Coordinates the pipeline
config.py               # Settings and environment variables
models.py               # Shared data models
scanner.py              # Finds and validates REC_#### files
game_blocks.py          # Detects complete games
concatenator.py         # Joins recordings with FFmpeg
youtube_publisher.py    # Uploads videos and metadata
archiver.py             # Moves successfully published recordings
tests/                  # Automated tests for the pipeline logic
output/                 # Local generated videos, excluded from Git
```

The Python modules are scaffolded with their responsibilities only. Behavior will be added one module at a time, beginning with discovery and block detection.

## Prerequisites

- Windows 10 or 11
- Python 3.11 or newer
- FFmpeg available on `PATH`
- A Google Cloud project with the YouTube Data API enabled
- OAuth credentials for the YouTube channel

## Local setup

Create the project virtual environment once from PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
```

Leave the environment with:

```powershell
deactivate
```

The YouTube API requires a one-time browser authorization. The refresh token and client secret will be kept outside the repository and excluded by `.gitignore`.

## Important safety rules

- Confirm the MicroSD card is actually mounted at `E:` before processing.
- Never delete source recordings automatically.
- Use a dry run to show detected blocks and planned moves before the first real run.
- Do not move files to `published` unless the corresponding YouTube upload completed successfully.
- Keep the generated videos outside `E:\DCIM\100_MEVO` so they cannot be mistaken for source recordings.

## Open decisions before implementation

- Exact definition of "short": the initial default can be less than 55 minutes, with a configurable threshold to allow for recording-start/stop variation.
- Team names and the preferred title/description format.
- Whether one run should upload every complete block or stop after one game.