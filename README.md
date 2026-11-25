# Medal Clip Renamer

Medal.tv gives video clips generated filenames and does not update those filenames when you change a clip's title in Medal. This tool reads the titles from Medal's local database and renames the corresponding video files on disk, so the filenames match the titles you chose.

## Requirements

- Windows
- Python 3.8 or newer
- No dependencies; the tool uses only the Python standard library.

Tested with Medal desktop on Windows, November 2026.

## Getting started

Download `rename_medal.py` (or clone this repository), then open a terminal in that folder. If `python` isn't recognized, try `py rename_medal.py`.

## Usage

1. Fully quit Medal first, including from the system tray, so no files are locked.
2. Run a dry run to review the proposed changes:

   ```powershell
   python rename_medal.py
   ```

   The dry run prints old and new filenames and changes nothing. If something looks off, run the dry run with `--debug` to print raw bytes for clips skipped because they have no title:

   ```powershell
   python rename_medal.py --debug
   ```

   Example dry-run output:

   ```text
   MedalTVLeagueofLegends20261122210849936.mp4 -> Ranked game - win.mp4
   MedalTVValorant20261122210912000.mp4 -> Clutch round.mp4
   MedalTVApexLegends20261122211034000.mp4 -> Final squad.mp4

   To rename: 3 | already named: 0 | no title (skipped): 2 | file not found: 0
   ```

3. When the proposed changes look right, apply them:

   ```powershell
   python rename_medal.py --apply
   ```

   This writes a `medal_rename_log_<timestamp>.csv` undo log in the script's folder. To restore the old filenames, pass that log to `--undo`:

   ```powershell
   python rename_medal.py --undo "<your log file>.csv"
   ```

   Keep the log until you're happy with the result, since it's the only way to undo.

To use a specific Medal database instead of the automatically selected one:

```powershell
python rename_medal.py --db "C:\path\to\medal-123.db"
```

## How it works

The tool finds Medal's local database, normally under `%APPDATA%\Medal\medal-<id>.db`, and copies it (including any SQLite `-wal` and `-shm` files) to a temporary folder. It never writes to the original database. From the copy, it reads each clip's file path from `contents.video_path` and its title from the binary metadata blob. Clips without a title are skipped; auto-generated titles such as `Player Slain - Rell` are kept. Characters that are illegal in Windows filenames are stripped. Renaming is a dry run by default; `--apply` performs the changes and records them in a CSV log that can be used with `--undo`.

Duplicate titles are numbered with the oldest clip keeping the plain name (`Title`, `Title (2)`, `Title (3)`). Files stay in their original folder and keep their extension. Screenshots and thumbnails are not touched. Clips whose files can't be found are reported but not changed. If you have multiple Medal accounts, use `--db` to select the database.

## Limitations

- Medal's metadata format is undocumented and was reverse-engineered from a small number of clips. It may break after a Medal update.
- This tool is Windows-only for now.
- Once renamed, Medal will no longer find those files. This is intended for an archive-then-clear-storage workflow.
- Always run the dry run first and review the proposed names before applying changes.

## Troubleshooting

If titles are missing or the proposed names look wrong, run `python rename_medal.py --debug` and open an issue with the output. Before posting, remove your Windows username from the database path and any clip names you don't want public; include your Python version and approximately when Medal was installed. Do not post your Medal database or any account data.

## AI disclosure

This tool was built with AI assistance: the script was written with Claude (by Anthropic), and GitHub Copilot helped with repository setup. The author tested it on real Medal clips on their own machine.

This is an unofficial tool and is not affiliated with Medal or Medal.tv.
