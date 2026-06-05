# WordHelper

A Flask web application for solving 5-letter word puzzles such as Wordle. Enter clues from your guesses and the tool filters a dictionary of ~16,000 words down to the remaining candidates.

## Features

- **Letter state controls** — mark each letter as excluded, known to be in the word, correct position, or wrong position
- **Live filtering** — the word list updates automatically as you adjust letter states
- **Letter frequency counts** — each letter card shows how many remaining words contain that letter in the current memory
- **Cross-memory counts** — a second count shows how many words contain that letter across all active memories combined (excludes unfiltered memories and memories already solved to one word)
- **Memory strip** — a row of 6 coloured dots on each letter card shows at a glance which memory slots still have that letter as a possibility
- **Visual dimming** — letters not present in any remaining word are dimmed automatically, without changing their state
- **6 memory slots** — save and restore independent search states, useful for multi-word variants like Quordle
- **Reset / Reset All** — reset the current memory slot or all slots at once
- **Keyboard shortcuts** — press any letter key A–Z to toggle that letter's enabled state

## Stack

- **Backend:** Python / Flask
- **Frontend:** Single-page HTML/CSS/JS (no framework)
- **Server:** Gunicorn (production), Flask dev server (development)
- **Packaging:** Maven assembly plugin, deployed via systemd

## Running locally

```bash
# Activate the virtual environment
source .venv/bin/activate

# Install dependencies (first time)
pip install -r requirements.txt

# Start the dev server
python app.py
```

App runs at `http://localhost:5000`.

## How it works

`words.txt` contains ~16,000 five-letter words. On startup Flask loads the list and computes letter frequencies, which determine the display order of letter cards (most common letters first).

The `/evaluate` endpoint receives the current letter states as JSON and filters the word list against four constraints:

| Constraint     | Meaning                                             |
|----------------|-----------------------------------------------------|
| Excluded       | Letter is not in the word                           |
| Pattern        | Letter is at a specific position                    |
| Must include   | Letter is in the word (position unknown)            |
| Exclude pattern| Letter is in the word but not at a specific position|

## Deployment

Packaged via `mvn release` and deployed to `/usr/bin/jbr/wordhelper` (production) or `/usr/bin/jbr/dev/wordhelper` (development). Pre/post deploy scripts in `src/main/resources/scripts/` stop and restart the `wordhelper` systemd service.
