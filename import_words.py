#!/usr/bin/env python3
"""
Import a word list into a SQLite database.

Usage:
    python import_words.py [--source PATH] [--db PATH] [--source-tag TAG] [--lowercase]

Defaults:
    --source      /usr/share/dict/british-english-huge
    --db          words.db
    --source-tag  wbritish
    --lowercase   off (preserve original case)

Examples:
    # Initial import from system dictionary
    python import_words.py

    # Import an additional word list as lowercase, tagged separately
    python import_words.py --source words.txt --source-tag wordlist --lowercase --db ~/words.db
"""

import argparse
import sqlite3
import sys
from pathlib import Path

DEFAULT_SOURCE = "/usr/share/dict/british-english-huge"
DEFAULT_DB = "/var/lib/wordhelper/words.db"
DEFAULT_TAG = "wbritish"

SCHEMA = """
CREATE TABLE IF NOT EXISTS words (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    word                TEXT    NOT NULL,
    length              INTEGER NOT NULL,
    is_proper           INTEGER NOT NULL DEFAULT 0,
    has_special         INTEGER NOT NULL DEFAULT 0,
    pos1                TEXT,
    pos2                TEXT,
    pos3                TEXT,
    pos4                TEXT,
    pos5                TEXT,
    unique_letter_count INTEGER,
    has_repeated        INTEGER NOT NULL DEFAULT 0,
    letter_set          TEXT,
    source              TEXT    NOT NULL DEFAULT 'wbritish',
    is_ascii            INTEGER NOT NULL DEFAULT 0
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_words_word       ON words(word);
CREATE        INDEX IF NOT EXISTS idx_words_length     ON words(length);
CREATE        INDEX IF NOT EXISTS idx_words_pos1       ON words(pos1);
CREATE        INDEX IF NOT EXISTS idx_words_pos2       ON words(pos2);
CREATE        INDEX IF NOT EXISTS idx_words_pos3       ON words(pos3);
CREATE        INDEX IF NOT EXISTS idx_words_pos4       ON words(pos4);
CREATE        INDEX IF NOT EXISTS idx_words_pos5       ON words(pos5);
CREATE        INDEX IF NOT EXISTS idx_words_letter_set ON words(letter_set);
CREATE        INDEX IF NOT EXISTS idx_words_flags      ON words(is_proper, has_special);
CREATE        INDEX IF NOT EXISTS idx_words_source     ON words(source);
CREATE        INDEX IF NOT EXISTS idx_words_is_ascii   ON words(is_ascii);
"""

WORD_INSERT = """
INSERT OR IGNORE INTO words
    (word, length, is_proper, has_special,
     pos1, pos2, pos3, pos4, pos5,
     unique_letter_count, has_repeated, letter_set, source, is_ascii)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

BATCH_SIZE = 5000


def migrate_schema(con: sqlite3.Connection):
    """Apply any pending column additions to an existing database."""
    tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "words" not in tables:
        return  # new DB — executescript will create it correctly

    cols = {row[1] for row in con.execute("PRAGMA table_info(words)")}

    if "source" not in cols:
        print("Migrating: adding 'source' column...")
        con.execute("ALTER TABLE words ADD COLUMN source TEXT NOT NULL DEFAULT 'wbritish'")
        con.execute("CREATE INDEX IF NOT EXISTS idx_words_source ON words(source)")
        con.commit()
        print("  Done.")

    if "is_ascii" not in cols:
        print("Migrating: adding 'is_ascii' column...")
        con.execute("ALTER TABLE words ADD COLUMN is_ascii INTEGER NOT NULL DEFAULT 0")
        con.execute("CREATE INDEX IF NOT EXISTS idx_words_is_ascii ON words(is_ascii)")
        print("  Populating is_ascii for existing rows...")
        rows = con.execute("SELECT id, word FROM words").fetchall()
        updates = [(1 if word.isascii() else 0, row_id) for row_id, word in rows]
        con.executemany("UPDATE words SET is_ascii = ? WHERE id = ?", updates)
        con.commit()
        print(f"  Updated {len(updates):,} rows. Done.")

    if "letter_stats" in tables:
        print("Migrating: dropping letter_stats table...")
        con.execute("DROP TABLE letter_stats")
        con.commit()
        print("  Done.")


def analyse(word: str, lowercase: bool, source_tag: str):
    """Return a full row tuple for a single word (already stripped)."""
    if lowercase:
        word = word.lower()

    is_proper = 1 if word[0].isupper() else 0
    is_ascii = 1 if word.isascii() else 0
    alpha_only = all(c.isalpha() for c in word)
    has_special = 0 if alpha_only else 1

    lower = word.lower()
    length = len(lower)

    pos1 = pos2 = pos3 = pos4 = pos5 = None
    unique_count = None
    has_repeated = 0
    letter_set = None

    if alpha_only:
        unique_letters = sorted(set(lower))
        unique_count = len(unique_letters)
        has_repeated = 1 if unique_count < length else 0
        letter_set = "".join(unique_letters)

        if length == 5:
            pos1, pos2, pos3, pos4, pos5 = lower

    return (word, length, is_proper, has_special,
            pos1, pos2, pos3, pos4, pos5,
            unique_count, has_repeated, letter_set, source_tag, is_ascii)


def import_words(source: Path, db_path: Path, source_tag: str, lowercase: bool):
    if not source.exists():
        print(f"Error: source file not found: {source}", file=sys.stderr)
        if source_tag == DEFAULT_TAG:
            print("Install with:  sudo apt install wbritish-huge", file=sys.stderr)
        sys.exit(1)

    con = sqlite3.connect(db_path)
    migrate_schema(con)
    con.executescript(SCHEMA)

    word_batch = []
    inserted = skipped = 0

    with source.open(encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            word = raw.strip()
            if not word:
                continue

            word_batch.append(analyse(word, lowercase, source_tag))

            if len(word_batch) >= BATCH_SIZE:
                cur = con.executemany(WORD_INSERT, word_batch)
                inserted += cur.rowcount
                skipped += len(word_batch) - cur.rowcount
                con.commit()
                word_batch.clear()
                print(f"  {inserted:,} inserted, {skipped:,} skipped...", end="\r")

    if word_batch:
        cur = con.executemany(WORD_INSERT, word_batch)
        inserted += cur.rowcount
        skipped += len(word_batch) - cur.rowcount
        con.commit()

    con.close()

    print(f"\nDone. {inserted:,} words inserted, {skipped:,} duplicates skipped.")
    print(f"Database: {db_path.resolve()}")


def main():
    parser = argparse.ArgumentParser(description="Import word list into SQLite")
    parser.add_argument("--source", default=DEFAULT_SOURCE,
                        help=f"Path to word list file (default: {DEFAULT_SOURCE})")
    parser.add_argument("--db", default=DEFAULT_DB,
                        help=f"Path to SQLite database (default: {DEFAULT_DB})")
    parser.add_argument("--source-tag", default=DEFAULT_TAG,
                        help=f"Tag to store in the source column (default: {DEFAULT_TAG})")
    parser.add_argument("--lowercase", action="store_true",
                        help="Force all words to lowercase before inserting")
    args = parser.parse_args()

    import_words(Path(args.source), Path(args.db), args.source_tag, args.lowercase)


if __name__ == "__main__":
    main()
