# WordHelper

A pair of Flask web applications for solving word puzzles, sharing a common word database and deployment directory.

---

## Apps

### WordHelper — port 5000

Solves 5-letter Wordle-style puzzles. Enter clues from your guesses and the tool filters the word list down to the remaining candidates.

**Features:**
- **Letter state controls** — mark each letter as excluded, known to be in the word, correct position, or wrong position
- **Live filtering** — the word list updates automatically as you adjust letter states
- **Letter frequency counts** — each letter card shows how many remaining words contain that letter
- **Cross-memory counts** — shows how many words contain that letter across all active memories combined
- **Memory strip** — a row of 6 coloured dots shows at a glance which memory slots still have that letter as a possibility
- **Visual dimming** — letters not present in any remaining word are dimmed automatically
- **6 memory slots** — independent search states, useful for multi-word variants like Quordle
- **Keyboard shortcuts** — press A–Z to toggle that letter's enabled state

### WordClue — port 5001

Finds words from partial clues. Useful for crosswords and general word puzzles.

**Features:**
- **Variable word length** — set the length from 3 to 20 letters
- **Known positions** — click a tile and type (or click) a letter to fix it at that position
- **Must-contain letters** — mark letters that must appear somewhere in the word
- **Excluded letters** — mark letters that are definitely not in the word
- **Linked positions** — group two or more positions by colour to indicate they must share the same (unknown) letter
- **Live results** — word list updates automatically as clues are adjusted

---

## Word Database

Both apps draw from a shared SQLite database at `/var/lib/wordhelper/words.db`, built from two sources:

| Source | Tag | Description |
|---|---|---|
| `wbritish-huge` system dictionary | `wbritish` | ~347k British English words |
| `words.txt` | `wordlist` | ~12.5k Scrabble word list (imported as lowercase) |

Words are filtered at runtime to `length`, `is_proper=0`, `has_special=0`, `is_ascii=1`.

See `WORD_DB.md` for full schema documentation and the `import_words.py` script for rebuilding or extending the database.

---

## Stack

- **Backend:** Python / Flask
- **Frontend:** Single-page HTML/CSS/JS (no framework)
- **Server:** Gunicorn (production), Flask dev server (development)
- **Database:** SQLite via Python `sqlite3`
- **Packaging:** Maven assembly plugin, deployed via systemd

---

## Running locally

```bash
# Activate the virtual environment
source .venv/bin/activate

# Install dependencies (first time)
pip install -r requirements.txt

# WordHelper (port 5000)
python app.py

# WordClue (port 5001)
python wordclue.py
```

---

## Deployment

Both apps are packaged via `mvn release` into a single zip and deployed to `/usr/bin/jbr/wordhelper` (production) or `/usr/bin/jbr/dev/wordhelper` (development). Each app runs as its own systemd service:

| Service | App | Port |
|---|---|---|
| `wordhelper.service` | `app.py` | 5000 |
| `wordclue.service` | `wordclue.py` | 5001 |
| `wordhelper-dev.service` | `app.py` | 5001 |
| `wordclue-dev.service` | `wordclue.py` | 5002 |

Pre/post deploy scripts in `src/main/resources/scripts/` stop and restart the services around each deployment.
