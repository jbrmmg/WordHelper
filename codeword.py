import io
import base64
import traceback
from collections import Counter

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from flask import Flask, render_template, request, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_prefix=1)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

ENGLISH_FREQ_ORDER = 'ETAOINSHRDLCUMWFGYPBVKJXQZ'

FONT_PATHS = [
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
    '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf',
]


def _load_font(size=13):
    for path in FONT_PATHS:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


# ── Grid detection ────────────────────────────────────────────────────────────

def find_grid_bounds(gray):
    """Find the outer extent of the grid by locating any very dark pixel."""
    very_dark = gray < 60
    row_has_dark = np.any(very_dark, axis=1)
    col_has_dark = np.any(very_dark, axis=0)

    if not np.any(row_has_dark) or not np.any(col_has_dark):
        h, w = gray.shape
        return 0, h - 1, 0, w - 1

    top    = int(np.argmax(row_has_dark))
    bottom = int(gray.shape[0] - 1 - np.argmax(row_has_dark[::-1]))
    left   = int(np.argmax(col_has_dark))
    right  = int(gray.shape[1] - 1 - np.argmax(col_has_dark[::-1]))
    return top, bottom, left, right


def classify_cell(gray, y0, y1, x0, x1, pad=4):
    """Return True if the cell interior is dark (blocked square)."""
    inner = gray[y0 + pad:y1 - pad, x0 + pad:x1 - pad]
    return inner.size == 0 or float(np.mean(inner)) < 160


# ── Visual pattern fingerprinting ─────────────────────────────────────────────

PATTERN_SIZE = 32   # pixels square for comparison image


def extract_corner(gray, y0, y1, x0, x1, pad=3):
    """Crop the top-left corner of a white cell (where the number lives)."""
    h = y1 - y0
    w = x1 - x0
    roi_h = max(4, int(h * 0.50) - pad)
    roi_w = max(4, int(w * 0.58) - pad)
    return gray[y0 + pad: y0 + pad + roi_h,
                x0 + pad: x0 + pad + roi_w]


def normalise_corner(crop):
    """
    Resize to PATTERN_SIZE x PATTERN_SIZE, threshold, and return a float32 array.
    The number pixels are made *dark* (0.0) on a white background (1.0).
    """
    resized = cv2.resize(crop, (PATTERN_SIZE, PATTERN_SIZE),
                         interpolation=cv2.INTER_AREA)
    _, binary = cv2.threshold(resized, 150, 255, cv2.THRESH_BINARY)
    # Normalise: 1.0 = white background, 0.0 = dark digit pixel
    return binary.astype(np.float32) / 255.0


def cluster_patterns(patterns, mse_thr=0.02):
    """
    Greedy centroid clustering by MSE on binary corner images.
    Returns (cluster_id_for_each_pattern, [centroid_array, ...])
    """
    centroids = []   # running-mean float32 flat arrays
    counts    = []   # how many in each cluster
    assigned  = []   # cluster id for each pattern

    for flat in patterns:
        best_k, best_mse = -1, float('inf')
        for k, c in enumerate(centroids):
            mse = float(np.mean((flat - c) ** 2))
            if mse < best_mse:
                best_mse, best_k = mse, k

        if best_k >= 0 and best_mse <= mse_thr:
            # Welford-style running mean
            n = counts[best_k] + 1
            centroids[best_k] += (flat - centroids[best_k]) / n
            counts[best_k] = n
            assigned.append(best_k)
        else:
            centroids.append(flat.copy())
            counts.append(1)
            assigned.append(len(centroids) - 1)

    return assigned, centroids


def centroid_to_png_b64(centroid_flat, scale=3):
    """Render a cluster centroid as a small base64-encoded PNG thumbnail."""
    img_arr = (centroid_flat.reshape(PATTERN_SIZE, PATTERN_SIZE) * 255).astype(np.uint8)
    # Upscale for display
    big = cv2.resize(img_arr, (PATTERN_SIZE * scale, PATTERN_SIZE * scale),
                     interpolation=cv2.INTER_NEAREST)
    pil_img = Image.fromarray(big, mode='L')
    buf = io.BytesIO()
    pil_img.save(buf, 'PNG')
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode('utf-8')


# ── Main analysis pipeline ────────────────────────────────────────────────────

def analyze_image(image_bytes):
    nparr = np.frombuffer(image_bytes, np.uint8)
    img   = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError('Cannot decode image — please upload a valid PNG or JPG.')
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    top, bottom, left, right = find_grid_bounds(gray)

    # Determine grid size (try 13; could support other sizes later)
    n = 13
    cell_h = (bottom - top) / n
    cell_w = (right - left) / n

    # Build grid
    grid = []        # list of rows; each cell: {'type','cluster_id','corner'}
    patterns  = []   # flat normalised pattern for each light cell, in order
    positions = []   # (r, c) for each light cell, in same order

    for r in range(n):
        row = []
        y0 = int(top + r * cell_h)
        y1 = int(top + (r + 1) * cell_h)
        for c in range(n):
            x0 = int(left + c * cell_w)
            x1 = int(left + (c + 1) * cell_w)
            if classify_cell(gray, y0, y1, x0, x1):
                row.append({'type': 'dark', 'cluster_id': -1})
            else:
                corner = extract_corner(gray, y0, y1, x0, x1)
                flat   = normalise_corner(corner).flatten()
                patterns.append(flat)
                positions.append((r, c))
                row.append({'type': 'light', 'cluster_id': None})
        grid.append(row)

    if not patterns:
        raise ValueError('No white cells found — check that the image is a codeword puzzle.')

    assigned, centroids = cluster_patterns(patterns)

    # Write cluster IDs back into grid
    for idx, (r, c) in enumerate(positions):
        grid[r][c]['cluster_id'] = assigned[idx]

    # Count cluster frequencies
    freq = Counter(assigned)

    return grid, freq, centroids, n


# ── Visualisation ─────────────────────────────────────────────────────────────

def render_grid(grid, n_rows, n_cols, freq, cell=44):
    """Render detected grid; label each white cell with its frequency rank."""
    # Rank clusters: 1 = most frequent
    rank_of = {cid: rank + 1
               for rank, (cid, _) in enumerate(freq.most_common())}

    b  = 1
    im = Image.new('RGB', (n_cols * cell + b, n_rows * cell + b), '#222222')
    dr = ImageDraw.Draw(im)
    fn = _load_font(13)

    for r, row in enumerate(grid):
        for c, cd in enumerate(row):
            x, y = c * cell + b, r * cell + b
            if cd['type'] == 'dark':
                dr.rectangle([x, y, x + cell - b, y + cell - b], fill='#555555')
            else:
                dr.rectangle([x, y, x + cell - b, y + cell - b], fill='white')
                cid = cd['cluster_id']
                if cid is not None and cid in rank_of:
                    dr.text((x + 3, y + 2), str(rank_of[cid]),
                            fill='#1a237e', font=fn)

    buf = io.BytesIO()
    im.save(buf, 'PNG')
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode('utf-8')


# ── Flask routes ──────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('codeword.html')


@app.route('/analyze', methods=['POST'])
def analyze():
    if 'image' not in request.files or not request.files['image'].filename:
        return jsonify({'error': 'No image uploaded'}), 400
    try:
        image_bytes = request.files['image'].read()
        grid, freq, centroids, n = analyze_image(image_bytes)

        grid_b64 = render_grid(grid, n, n, freq)

        total = sum(freq.values())
        freq_list = []
        for rank, (cid, count) in enumerate(freq.most_common()):
            freq_list.append({
                'rank':        rank + 1,
                'cluster_id':  cid,
                'count':       count,
                'percentage':  round(100 * count / total, 1) if total else 0,
                'letter_hint': ENGLISH_FREQ_ORDER[rank] if rank < 26 else '?',
                'thumbnail':   centroid_to_png_b64(centroids[cid]),
            })

        return jsonify({
            'grid_image': grid_b64,
            'frequency':  freq_list,
            'stats': {
                'n_rows':         n,
                'n_cols':         n,
                'total_active':   total,
                'patterns_found': len(freq),
            },
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
