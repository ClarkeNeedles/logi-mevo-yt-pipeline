# Logi Mevo to YouTube Pipeline

Turn Logi Mevo recordings from a MicroSD card into public YouTube videos for the team.

## Table of contents

- [Workflow](#workflow)
- [Project structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Local setup](#local-setup)
- [OAuth and YouTube setup](#oauth-and-youtube-setup)
- [Running the tool](#running-the-tool)
- [Important safety rules](#important-safety-rules)

## Workflow

The pipeline will run on Windows and use the card mounted as `E:`:

1. The pipeline scans `E:\DCIM\100_MEVO` for files named `REC_0001`, `REC_0002`, and so on. It considers only completed video files matching the expected naming pattern.
2. The pipeline sorts the recordings by their numeric recording number, not by filename text or filesystem date.
3. The pipeline treats recordings as game blocks. A block contains one or more recordings of about one hour and ends at the first recording shorter than one hour. For example:

	```text
	REC_0001  1 hour
	REC_0002  1 hour
	REC_0003  34 minutes  <- Game 1 ends here
	REC_0004  1 hour
	REC_0005  1 hour
	REC_0006  41 minutes  <- Game 2 ends here
	```

4. The pipeline does not process an incomplete block. If the final recording is still about one hour, it waits until a shorter recording appears.
5. The pipeline concatenates each complete block in order, without re-encoding when the input files are compatible.
6. The pipeline creates an output filename containing the date and game number, for example `2026-08-28-game-1.mp4` and `2026-08-28-game-2.mp4`.
7. The pipeline creates a YouTube title containing:
	- the two team names;
	- the game date;
	- `Game 1`, `Game 2`, etc.
8. The pipeline uploads the finished video to the configured YouTube channel with visibility set to `public`. YouTube selects a frame from the video automatically because no custom thumbnail is supplied.
9. The pipeline moves every source recording used successfully for the upload into `E:\DCIM\100_MEVO\published`. This keeps old `REC_####` files out of the next run, so a new card recording can start again at `REC_0001`.

Source recordings must be moved only after concatenation and YouTube upload succeed. If a step fails, leave the source files in place so the run can be retried.

## Project structure

```text
main.py                 # Coordinates scanning, processing, publishing, and archiving
config.py               # Application configuration module
models.py               # Shared recording, game-block, and upload models
scanner.py              # Finds recordings and reads their metadata
game_blocks.py          # Detects complete game blocks
concatenator.py         # Joins recordings with FFmpeg
youtube_publisher.py    # Authenticates and uploads videos to YouTube
archiver.py             # Moves successfully published recordings
requirements.txt        # Python package dependencies
.env.example            # Configuration template
.env                    # Personal configuration, excluded from Git
.venv/                  # Local virtual environment, excluded from Git
credentials/            # OAuth files, excluded from Git
output/                 # Local generated videos, excluded from Git
```

The scanning, game-block detection, concatenation, team-name prompting, YouTube publishing, and archiving flow is implemented. A normal run publishes without a confirmation prompt; use `--confirm-before-publish` when you want to review the first upload.

## Prerequisites

- Windows 10 or 11
- Python 3.11 or newer
- FFmpeg and FFprobe installed, with their directory configured by `FFMPEG_BIN_DIR`
- A Google Cloud project with the YouTube Data API enabled
- OAuth credentials for the YouTube channel

## Local setup

Install FFmpeg, which provides both `ffmpeg.exe` and `ffprobe.exe`, from PowerShell:

```powershell
winget install --id Gyan.FFmpeg.Shared
```

Open a new PowerShell window after installation and verify the executables:

```powershell
ffmpeg -version
ffprobe -version
```

Create the project virtual environment once from PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
```

Copy the environment template and update `FFMPEG_BIN_DIR` in your local `.env` file. Set it to the directory containing both `ffmpeg.exe` and `ffprobe.exe`, not to either executable itself:

```powershell
Copy-Item .env.example .env
Get-Command ffmpeg | Select-Object -ExpandProperty Source
```

For example, if the command reports `C:\ffmpeg\bin\ffmpeg.exe`, set:

```text
FFMPEG_BIN_DIR=C:\ffmpeg\bin
```

If winget installs FFmpeg in a different directory, replace the example value with that actual directory path in `.env`.

## OAuth and YouTube setup

The publisher uses the YouTube Data API with OAuth 2.0. These steps only need to be completed once for each computer and Google account.

### Create a Google Cloud project

1. Open the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project or select an existing project.
3. Open **APIs & Services > Library**.
4. Search for **YouTube Data API v3** and click **Enable**.

### Configure the OAuth consent screen

1. Open **APIs & Services > OAuth consent screen**.
2. Choose **External** unless this is a Google Workspace-only application.
3. Enter an app name and the requested contact information.
4. Add your Google account as a test user if the app is in testing mode.
5. Use the YouTube upload scope when prompted:

	```text
	https://www.googleapis.com/auth/youtube.upload
	```

### Download the client secret

1. Open **APIs & Services > Credentials**.
2. Click **Create Credentials > OAuth client ID**.
3. Choose **Desktop app**.
4. Download the JSON file.
5. Create this directory in the project root:

	```text
	credentials/
	```

6. Rename the downloaded JSON file to `client_secret.json` and place it here:

	```text
	credentials/client_secret.json
	```

### Create your local environment file

Do not edit `.env.example` directly. Copy it to `.env`, then customize `.env` for your computer:

```powershell
Copy-Item .env.example .env
```

The relevant settings are:

```text
FFMPEG_BIN_DIR=C:\ffmpeg\bin
YOUTUBE_CATEGORY_ID=17
YOUTUBE_PRIVACY_STATUS=public
YOUTUBE_CLIENT_SECRETS_FILE=credentials/client_secret.json
YOUTUBE_TOKEN_FILE=credentials/token.json
```

The paths are relative to the project directory. `token.json` does not need to be created manually. On the first real upload, the script will open a browser for Google authorization and create it automatically after authorization succeeds. Later runs reuse that token.

The `.env` file, client secret, and token are private and are excluded from Git by `.gitignore`. Never commit them or share them with other users.

### Add yourself as a test user

After the Google Cloud project, OAuth consent screen, client secret, and `.env` file are set up:

1. Return to **APIs & Services > OAuth consent screen** in Google Cloud Console.
2. Find the **Test users** section.
3. Click **Add users** and enter the Google account that owns or manages the YouTube channel.
4. Save the change.

The account used during the first browser authorization must be listed as a test user while the app remains in testing mode. Otherwise Google returns `Error 403: access_denied`.

## Running the tool

Run the tool from the project root after activating the virtual environment:

```powershell
python main.py
```

The tool will:

1. Scan the configured Mevo directory for recordings.
2. Find complete game blocks.
3. Ask for the home and away team names.
4. Concatenate each complete game.
5. Upload each game to YouTube.
6. Move the successfully uploaded source recordings into `published`.

The normal run does not ask for an additional confirmation before publishing. Use the dry run first when reviewing a new recording batch:

```powershell
python main.py --dry-run
```

Dry-run mode scans the recordings, detects game blocks, displays the planned titles and output files, and does not concatenate, upload, or move files.

The YouTube API requires a one-time browser authorization. The refresh token and client secret will be kept outside the repository and excluded by `.gitignore`.

### Command-line flags

| Flag | Default | Description |
| --- | --- | --- |
| `--help` | N/A | Show all available options and exit. |
| `--source-dir PATH` | `E:\DCIM\100_MEVO` or `MEVO_SOURCE_DIR` | Directory containing `REC_####` recordings. |
| `--output-dir PATH` | `output` or `OUTPUT_DIR` | Directory for concatenated game videos. |
| `--published-dir PATH` | `E:\DCIM\100_MEVO\published` or `PUBLISHED_DIR` | Directory where successfully uploaded source recordings are moved. |
| `--confirm-before-publish` | Off | Ask for confirmation before the first YouTube upload. Without this flag, publishing is unattended after the team-name prompts. |
| `--dry-run` | Off | Show the detected games and planned outputs without concatenating, uploading, or archiving. |

For example, to process a different card location while keeping the default output and archive locations:

```powershell
python main.py --source-dir "F:\DCIM\100_MEVO"
```

To review all detected games before allowing any upload:

```powershell
python main.py --confirm-before-publish
```

## Important safety rules

- Confirm the MicroSD card is actually mounted at `E:` before processing.
- Never delete source recordings automatically.
- Use a dry run to show detected blocks and planned moves before the first real run.
- Run with `--confirm-before-publish` when you want to approve the detected games before the first upload.
- Do not move files to `published` unless the corresponding YouTube upload completed successfully.
- Keep the generated videos outside `E:\DCIM\100_MEVO` so they cannot be mistaken for source recordings.