# WordHelper

A Flask web application for solving word-based puzzles (primarily Wordle-style 5-letter word games). The UI lets the user mark letters as excluded, required, or positionally correct/incorrect, then filters a ~16k-word dictionary to show matching candidates.

## Project Structure

- `app.py` — Flask app; loads `words.txt` at startup, serves the UI, and handles the `/evaluate` POST endpoint
- `templates/index.html` — Single-page UI (plain HTML/CSS/JS, no framework)
- `words.txt` — ~16k five-letter words used as the dictionary
- `requirements.txt` — Python dependencies (Flask, Gunicorn)
- `pom.xml` — Maven config for packaging and release (not Python-specific)

## Running the App

```bash
# Development
python app.py
# Runs on http://localhost:5000 in debug mode

# Production (via systemd + gunicorn)
gunicorn -w 2 -b 127.0.0.1:5000 app:app
```

The `.venv` directory contains the virtual environment. Activate it with:
```bash
source .venv/bin/activate
```

## How the Backend Works

`load_words()` reads `words.txt` at startup, filters to 5-letter words, and builds a letter-frequency ordering used to sort the UI's letter cards.

`check_word()` filters candidate words against four constraints:
- `excluded` — letters that must not appear
- `pattern` — exact position matches (e.g. `_A___`)
- `must_include` — letters that must appear somewhere
- `exclude_patterns` — per-letter wrong-position exclusions

The `/evaluate` endpoint receives a JSON payload of letter states from the UI and returns matching words, count, and a summary of active constraints.

## Deployment

Deployed via Maven release to `/usr/bin/jbr/wordhelper` (production) or `/usr/bin/jbr/dev/wordhelper` (dev). Pre/post deploy scripts in `src/main/resources/scripts/` stop/start the systemd service (`wordhelper.service`).

## Tests

No test suite exists yet.

## Branch / Release Convention

- Main branch for PRs: `Release`
- Versions managed by `maven-release-plugin` (e.g. `v26.3.9`)
- Feature branches follow the pattern `feature/JBR-NNN`
