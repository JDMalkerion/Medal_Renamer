"""
Rename Medal clip files to the titles you set inside Medal.

How it works
  - Copies Medal's database (plus -wal/-shm) to a temp folder and reads the copy.
    Medal's own files are never modified.
  - For every clip, reads the title out of the `metadata` blob and the file
    location from `video_path`.
  - Clips with NO title are skipped. Auto-generated titles (e.g. "Player Slain - Rell")
    are kept and used as the new name.
  - Duplicate titles get a number: "Title", "Title (2)", "Title (3)" (oldest clip first).
  - Dry run by default. Nothing is renamed until you pass --apply.
  - Every rename is written to a CSV log so it can be undone with --undo.

Usage (close Medal first):
    python rename_medal_clips.py                      dry run, prints old -> new
    python rename_medal_clips.py --apply              actually rename
    python rename_medal_clips.py --undo LOGFILE.csv   put the old names back
    python rename_medal_clips.py --db "C:\\path\\medal-123.db"   use a specific database
    python rename_medal_clips.py --debug              show raw bytes for skipped clips
"""
import argparse
import csv
import glob
import os
import re
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime

BAD_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
RESERVED = {"CON", "PRN", "AUX", "NUL"}
RESERVED.update(f"COM{i}" for i in range(1, 10))
RESERVED.update(f"LPT{i}" for i in range(1, 10))
MAX_STEM = 120


def find_db():
    appdata = os.environ.get("APPDATA", "")
    found = [p for p in glob.glob(os.path.join(appdata, "*", "medal-*.db"))
             if "guest" not in os.path.basename(p).lower()]
    if not found:
        return None
    found.sort(key=os.path.getmtime, reverse=True)
    return found[0]


def copy_db(path):
    tmp = tempfile.mkdtemp(prefix="medal_rename_")
    base = os.path.basename(path)
    for suffix in ("", "-wal", "-shm"):
        src = path + suffix
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(tmp, base + suffix))
    return os.path.join(tmp, base)


def extract_title(blob):
    """Read the value that follows the 'title' key in Medal's metadata blob.

    Observed encodings: titles are stored as 0xC7, <length byte>, <utf-8 bytes>.
    A few other string prefixes are handled too. Returns None if there is no title.
    """
    if blob is None:
        return None
    if isinstance(blob, str):
        blob = blob.encode("utf-8", "ignore")
    i = blob.find(b"title")
    if i == -1:
        return None
    j = i + 5
    if j >= len(blob):
        return None
    tag = blob[j]
    if tag == 0xC7 or tag == 0xD9:                 # 1-byte length
        n = blob[j + 1]
        data = blob[j + 2:j + 2 + n]
    elif tag == 0xC8 or tag == 0xDA:               # 2-byte length
        n = int.from_bytes(blob[j + 1:j + 3], "big")
        data = blob[j + 3:j + 3 + n]
    elif 0xA0 <= tag <= 0xBF:                      # short string
        n = tag & 0x1F
        data = blob[j + 1:j + 1 + n]
    else:
        return None
    try:
        text = data.decode("utf-8").strip()
    except UnicodeDecodeError:
        return None
    return text or None


def safe_stem(title):
    s = BAD_CHARS.sub("", title)
    s = re.sub(r"\s+", " ", s).strip(" .")
    s = s[:MAX_STEM].rstrip(" .")
    if s.upper() in RESERVED:
        s += "_"
    return s


def load_rows(db_copy):
    con = sqlite3.connect(db_copy)
    try:
        cur = con.cursor()
        cur.execute(
            "SELECT created_at, local_content_id, video_path, metadata "
            "FROM contents WHERE video_path IS NOT NULL AND video_path != '' "
            "ORDER BY created_at"
        )
        return cur.fetchall()
    finally:
        con.close()


def build_plan(rows, debug=False):
    plan, no_title, missing, already = [], [], [], 0
    used = {}  # folder -> set of lowercase filenames claimed by this plan

    for created_at, lid, vpath, blob in rows:
        title = extract_title(blob)
        stem = safe_stem(title) if title else ""
        if not stem:
            no_title.append((vpath, blob))
            continue
        if not os.path.isfile(vpath):
            missing.append(vpath)
            continue

        folder, old_name = os.path.split(vpath)
        ext = os.path.splitext(old_name)[1]
        taken = used.setdefault(os.path.normcase(folder), set())

        n = 1
        while True:
            new_name = stem + ("" if n == 1 else f" ({n})") + ext
            low = new_name.lower()
            if new_name == old_name:
                taken.add(low)
                already += 1
                new_name = None
                break
            if low not in taken and not os.path.exists(os.path.join(folder, new_name)):
                taken.add(low)
                break
            n += 1

        if new_name:
            plan.append((vpath, os.path.join(folder, new_name)))

    return plan, no_title, missing, already


def do_apply(plan):
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            f"medal_rename_log_{stamp}.csv")
    done, failed = 0, 0
    with open(log_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["old_path", "new_path"])
        for old, new in plan:
            try:
                os.rename(old, new)
                w.writerow([old, new])
                f.flush()
                done += 1
            except OSError as e:
                failed += 1
                print(f"  FAILED: {os.path.basename(old)}  ({e})")
    print(f"\nRenamed {done} file(s), {failed} failed.")
    print(f"Undo log: {log_path}")


def do_undo(log_path):
    done = 0
    with open(log_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            old, new = row["old_path"], row["new_path"]
            if os.path.exists(new) and not os.path.exists(old):
                try:
                    os.rename(new, old)
                    done += 1
                except OSError as e:
                    print(f"  FAILED: {os.path.basename(new)}  ({e})")
            else:
                print(f"  Skipped (not found or old name already exists): {os.path.basename(new)}")
    print(f"\nRestored {done} file(s).")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--db")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--undo")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    if args.undo:
        do_undo(args.undo)
        return

    path = args.db or find_db()
    if not path or not os.path.exists(path):
        print('Could not find the Medal database. Use --db "C:\\full\\path\\medal-XXXX.db"')
        sys.exit(1)
    print("Database:", path)

    rows = load_rows(copy_db(path))
    plan, no_title, missing, already = build_plan(rows, args.debug)

    for old, new in plan:
        print(f"{os.path.basename(old)}  ->  {os.path.basename(new)}")

    if args.debug:
        print("\nSkipped (no title) raw bytes after 'title':")
        for vpath, blob in no_title:
            i = blob.find(b"title") if blob else -1
            snippet = blob[i + 5:i + 29].hex(" ") if i != -1 else "(no 'title' key)"
            print(f"  {os.path.basename(vpath)}: {snippet}")

    print(f"\nTo rename: {len(plan)} | already named: {already} | "
          f"no title (skipped): {len(no_title)} | file not found: {len(missing)}")
    if missing:
        print("Files listed in Medal but missing on disk (moved, deleted, or already renamed):")
        for m in missing[:10]:
            print("  ", m)
        if len(missing) > 10:
            print(f"   ...and {len(missing) - 10} more")

    if not plan:
        return
    if args.apply:
        do_apply(plan)
    else:
        print("\nDRY RUN: nothing was renamed. Add --apply to rename for real.")


if __name__ == "__main__":
    main()