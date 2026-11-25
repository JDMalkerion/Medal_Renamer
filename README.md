# Medal Clip Renamer

Medal.tv gives video clips generated filenames and does not update those filenames when you change a clip's title in Medal. This tool reads the titles from Medal's local database and renames the corresponding video files on disk, so the filenames match the titles you chose.

## Requirements

- Windows
- Python 3.8 or newer
- No dependencies; the tool uses only the Python standard library.

## Usage

1. Close Medal first.
2. Run a dry run to review the proposed changes:

   ```powershell
   python rename_medal.py
   ```

   The dry run prints old and new filenames and changes nothing. If something looks off, run the dry run with `--debug` to print raw bytes for clips skipped because they have no title:

   ```powershell
   python rename_medal.py --debug
   ```

3. When the proposed changes look right, apply them:

   ```powershell
   python rename_medal.py --apply
   ```

   This writes a `medal_rename_log_<timestamp>.csv` undo log in the script's folder. To restore the old filenames, pass that log to `--undo`:

   ```powershell
   python rename_medal.py --undo "medal_rename_log_20261125_092616.csv"
   ```

To use a specific Medal database instead of the automatically selected one:

```powershell
python rename_medal.py --db "C:\path\to\medal-123.db"
```

## How it works

The tool finds Medal's local database, normally under `%APPDATA%\Medal\medal-<id>.db`, and copies it (including any SQLite `-wal` and `-shm` files) to a temporary folder. It never writes to the original database. From the copy, it reads each clip's file path from `contents.video_path` and its title from the binary metadata blob. Clips without a title are skipped; auto-generated titles such as `Player Slain - Rell` are kept. Duplicate titles are numbered, and characters that are illegal in Windows filenames are stripped. Renaming is a dry run by default; `--apply` performs the changes and records them in a CSV log that can be used with `--undo`.

## Limitations

- Medal's metadata format is undocumented and was reverse-engineered from a small number of clips. It may break after a Medal update.
- This tool is Windows-only for now.
- Once renamed, Medal will no longer find those files. This is intended for an archive-then-clear-storage workflow.
- Always run the dry run first and review the proposed names before applying changes.

## Troubleshooting

If titles are missing or the proposed names look wrong, run `python rename_medal.py --debug` and open an issue with the output. Do not post your Medal database or any account data.

This is an unofficial tool and is not affiliated with Medal or Medal.tv.
