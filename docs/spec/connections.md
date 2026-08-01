# JBR-692 Connections Puzzle Helper — Specification

## Purpose

A browser-based tool for working through the NY Times Connections puzzle. The puzzle presents 16 words that must be sorted into 4 groups of exactly 4, where each group shares a hidden theme. This tool lets you:

- Enter the 16 puzzle words
- Colour-code each word into its candidate group (yellow / green / blue / purple)
- Add research notes against individual words
- See at a glance how many words are assigned to each group (max 4 per group)

It is a single-user thinking aid — there is no multi-player state or puzzle database.

---

## Technology Stack

Consistent with the existing `wordhelper` and `wordclue` tools:

| Layer       | Technology                                   |
|-------------|----------------------------------------------|
| Backend     | Python 3.12, Flask, Gunicorn (2 workers)     |
| Frontend    | Plain HTML / CSS / JS — no framework         |
| Container   | Docker (python:3.12-slim base), port 8080    |
| Reverse proxy | nginx (`/connections/` prefix)             |

No word database is needed. All puzzle state is held in the browser (`localStorage`) so the page survives a refresh.

---

## Application Structure

```
connections/
├── connections.py          # Flask app (serves one route)
├── templates/
│   └── connections.html    # Single-page UI
├── static/
│   └── connections.css     # Optional extracted styles
├── requirements.txt        # Flask, gunicorn (reuse existing file)
└── docker/
    └── Dockerfile-connections
```

---

## UI Design

### Layout — two phases

#### Phase 1: Word Entry

Shown when no words have been saved yet (or after "Reset").

- A 4×4 grid of plain text inputs (16 cells).
- A **Start** button that validates all 16 cells are non-empty and unique, then transitions to Phase 2.
- An optional **Paste** helper: user pastes a newline- or comma-separated list of 16 words; the tool fills the grid automatically.

#### Phase 2: Working Board

The main puzzle-solving view.

```
┌─────────────────────────────────────────────────────────────────┐
│  Connections Helper                                             │
│                                                                 │
│  Groups: ● Yellow 0/4  ● Green 0/4  ● Blue 0/4  ● Purple 0/4  │
│                                                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │  WORD01  │ │  WORD02  │ │  WORD03  │ │  WORD04  │          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
│  ┌──────────┐  ...                                              │
│  │  WORD05  │                                                   │
│  └──────────┘                                                   │
│       ⋮                                                         │
│                                                                 │
│  [ Reset ]                                                      │
└─────────────────────────────────────────────────────────────────┘
```

**Word cards** (16 total, 4×4 grid):

- Displayed as a rounded card, word text centred and upper-cased.
- Background colour reflects the assigned group:
  - Unassigned → light grey
  - Yellow group → `#f9df6d` (NYT yellow)
  - Green group → `#a0c35a` (NYT green)
  - Blue group → `#b0c4ef` (NYT blue)
  - Purple group → `#ba81c5` (NYT purple)
- **Assigning a group — two methods (both supported):**
  1. **Click to cycle:** clicking a card steps through: unassigned → yellow → green → blue → purple → unassigned.
  2. **Drag and drop:** a card can be dragged onto any of the four group-header badges. Dropping it assigns it to that group. Cards within the board can also be dragged onto each other to swap positions (useful for visual organisation).
  - Both methods are blocked when the target group already has 4 words; a brief shake/flash animation indicates the block.
- A small **note icon** (✎) on each card opens an inline text area below the card where the user can type research notes. Notes persist in `localStorage`. The icon is highlighted when a note exists.

**Group counters** (header bar):

- Four coloured badges showing `n/4`. Turns bold/outlined when a group is full (4 words).
- The badges also act as drag-and-drop targets: dragging a word card onto a badge assigns it to that group.

#### Phase 3: Solved State

Triggered automatically when all 16 words have been assigned to a group (all four counters read 4/4). The board transitions to a tidy solved view:

- The 4×4 mixed grid is replaced by **four horizontal rows**, one per group, in the standard NYT order (yellow → green → blue → purple).
- Each row has a full-width coloured background (matching the group colour) and shows:
  - A **category title** field — an editable text input so the user can type the theme they discovered (e.g. "Types of snake").
  - The **four words** for that group displayed as chips.
  - A **Notes** toggle that expands to show all four per-word notes in a compact list below the row.
- An **Unsolved** button at the bottom returns to Phase 2 (the working board) so the user can adjust assignments.
- The solved layout is also persisted in `localStorage`, so refreshing the page after solving shows the solved view directly.

**Reset button**: present in both Phase 2 and Phase 3. Clears all group assignments, notes, and category titles, and returns to Phase 1. Asks for confirmation before proceeding.

---

## State Management

All state lives in `localStorage` under a single key `connections_state`:

```json
{
  "words": ["WORD1", ..., "WORD16"],
  "assignments": {
    "WORD1": "yellow",
    "WORD2": null
  },
  "notes": {
    "WORD1": "Could relate to types of fish"
  },
  "titles": {
    "yellow": "Types of fish",
    "green": "",
    "blue": "",
    "purple": ""
  }
}
```

The page reads this on load. If `words` is present it skips Phase 1 and goes straight to the board. Reset clears the key.

---

## Backend

The Flask app has a single route: serve the page. No API endpoints are needed — all logic runs in the browser.

```python
# connections.py
from flask import Flask, render_template
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_prefix=1)

@app.route('/')
def index():
    return render_template('connections.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)
```

---

## Dockerfile

`docker/Dockerfile-connections`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY connections.py ./
COPY templates/ templates/
COPY static/ static/

EXPOSE 8080

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8080", "connections:app"]
```

---

## docker-compose Changes

Add to `docker-compose.yml`:

```yaml
  connections:
    image: nexus.jbrmmg.me.uk:8084/connections:latest
    container_name: connections
    restart: unless-stopped
    networks:
      - jbr-network
```

Add to `docker-compose-dev.yml`:

```yaml
  connections-dev:
    image: nexus.jbrmmg.me.uk:8084/connections-dev:latest
    container_name: connections-dev
    restart: unless-stopped
    networks:
      jbr-network:
        aliases:
          - connections
```

---

## nginx Changes

Add to `nginx.conf.template` (in the Python web apps section, alongside `/wordhelper/` and `/wordclue/`):

```nginx
location /connections/ {
    set $upstream_connections connections:8080;
    rewrite            ^/connections/(.*)  /$1 break;
    proxy_pass         http://$upstream_connections;
    proxy_http_version 1.1;
    proxy_set_header   Host                $host;
    proxy_set_header   X-Real-IP           $remote_addr;
    proxy_set_header   X-Forwarded-For     $proxy_add_x_forwarded_for;
    proxy_set_header   X-Forwarded-Proto   $scheme;
    proxy_set_header   X-Forwarded-Prefix  /connections;
}
```

---

## CI/CD Changes

Add two steps to `.github/workflows/build.yml` (mirroring the `wordclue` steps):

```yaml
- name: Build connections Docker image
  run: |
    docker build \
      -f docker/Dockerfile-connections \
      -t nexus.jbrmmg.me.uk:8083/connections:${{ github.sha }} \
      -t nexus.jbrmmg.me.uk:8083/connections:latest \
      .

# (push step also needs connections tags added)
```

---

## Notes

- **Single puzzle only**: one puzzle at a time in `localStorage`. No save slots or history — Reset and re-enter words for a new puzzle.
- **requirements.txt**: The existing file is shared between `wordhelper` and `wordclue`. The connections app needs only `Flask` and `gunicorn`, so the same file works unchanged.
