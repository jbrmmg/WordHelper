# Word Database

SQLite database of English words for puzzle solving, imported from the `wbritish-huge` system dictionary.

## Location

The database is stored at `/var/lib/wordhelper/words.db`, owned by root and globally readable. Write access (for imports) requires `sudo`.

## Source

The `wbritish-huge` package provides a large British English word list at `/usr/share/dict/british-english-huge`.

Install it on Ubuntu/Debian with:

```bash
sudo apt install wbritish-huge
```

## Import Script

`import_words.py` reads a word list and populates the database. It accepts four arguments:

| Argument | Default | Description |
|---|---|---|
| `--source` | `/usr/share/dict/british-english-huge` | Path to the word list file |
| `--db` | `/var/lib/wordhelper/words.db` | Path to the SQLite database |
| `--source-tag` | `wbritish` | Value written to the `source` column |
| `--lowercase` | off | Force all words to lowercase before inserting |

```bash
# Initial import from system dictionary (source = 'wbritish')
sudo python import_words.py

# Import an additional word list as lowercase (source = 'wordlist')
sudo python import_words.py --source words.txt --source-tag wordlist --lowercase
```

Words are inserted in batches of 5,000 with progress reported to stdout. Duplicate words are silently skipped (`INSERT OR IGNORE`), so re-running the script against an existing database is safe. The script applies any pending schema migrations automatically on each run (adding missing columns, dropping obsolete tables).

## Schema

### `words`

One row per word from the source file.

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto-increment primary key |
| `word` | TEXT UNIQUE | Original word as it appears in the source file |
| `length` | INTEGER | Character length of the word |
| `is_proper` | INTEGER | 1 if the word starts with an uppercase letter |
| `has_special` | INTEGER | 1 if the word contains non-alpha characters (apostrophes, hyphens, etc.) |
| `pos1`–`pos5` | TEXT | Individual letters at each position; populated only for 5-letter pure-alpha words |
| `unique_letter_count` | INTEGER | Number of distinct letters; populated for pure-alpha words |
| `has_repeated` | INTEGER | 1 if the word contains any repeated letter |
| `letter_set` | TEXT | Sorted unique letters, e.g. `abck` for `aback`; populated for pure-alpha words |
| `source` | TEXT | Origin of the word: `wbritish` (from `wbritish-huge`) or `wordlist` (from `words.txt`) |
| `is_ascii` | INTEGER | 1 if the word contains only ASCII characters (A–Z, no accented letters) |

### Indexes

| Index | Columns | Purpose |
|---|---|---|
| `idx_words_word` | `word` (unique) | Primary lookup |
| `idx_words_length` | `length` | Filter by word length |
| `idx_words_pos1`–`pos5` | `pos1`–`pos5` | Pattern matching (known letter positions) |
| `idx_words_letter_set` | `letter_set` | Anagram / must-include queries |
| `idx_words_flags` | `is_proper, has_special` | Filter to puzzle-suitable words |
| `idx_words_source` | `source` | Filter by word origin |
| `idx_words_is_ascii` | `is_ascii` | Filter to ASCII-only words |

## Example Queries

Filter to Wordle-suitable words (5-letter, lowercase, ASCII only):

```sql
SELECT word FROM words
WHERE length = 5
  AND is_proper = 0
  AND has_special = 0
  AND is_ascii = 1;
```

Words matching a Wordle pattern — `_A_E_` (A in position 2, E in position 4):

```sql
SELECT word FROM words
WHERE length = 5 AND is_proper = 0 AND has_special = 0
  AND pos2 = 'a'
  AND pos4 = 'e';
```

Words that must contain certain letters with no repeated letters (good opening guesses):

```sql
SELECT word FROM words
WHERE length = 5 AND is_proper = 0 AND has_special = 0
  AND has_repeated = 0
  AND letter_set LIKE '%e%'
  AND letter_set LIKE '%a%'
  AND letter_set LIKE '%r%';
```

Words from the original `words.txt` word list only:

```sql
SELECT word FROM words WHERE source = 'wordlist';
```

