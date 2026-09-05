import io
import re
import base64
import traceback
from collections import Counter

import cv2
import numpy as np
import pytesseract
from PIL import Image, ImageDraw, ImageFont
from flask import Flask, render_template, request, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_prefix=1)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB

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


def _detect_lines_at(gray, thr):
    """Detect horizontal/vertical grid line positions using morphological opening."""
    h, w = gray.shape
    _, inv = cv2.threshold(gray, thr, 255, cv2.THRESH_BINARY_INV)

    # A grid line spans (almost) the full width/height; dark cells do not.
    h_mask = cv2.morphologyEx(inv, cv2.MORPH_OPEN,
                              cv2.getStructuringElement(cv2.MORPH_RECT, (w // 4, 1)))
    v_mask = cv2.morphologyEx(inv, cv2.MORPH_OPEN,
                              cv2.getStructuringElement(cv2.MORPH_RECT, (1, h // 4)))

    def band_centers(mask, axis):
        profile = np.any(mask > 0, axis=axis)
        centers, in_band, start = [], False, 0
        for i, active in enumerate(profile):
            if active and not in_band:
                start, in_band = i, True
            elif not active and in_band:
                centers.append((start + i) // 2)
                in_band = False
        if in_band:
            centers.append((start + len(profile)) // 2)
        return centers

    return band_centers(h_mask, axis=1), band_centers(v_mask, axis=0)


def find_grid_lines(gray):
    """Try progressively higher thresholds; fall back to a 13×13 estimate."""
    h, w = gray.shape
    for thr in (70, 100, 130):
        hl, vl = _detect_lines_at(gray, thr)
        if len(hl) >= 4 and len(vl) >= 4:
            return hl, vl
    mg = min(h, w) // 60
    n = 13
    return (
        [mg + i * (h - 2 * mg) // n for i in range(n + 1)],
        [mg + i * (w - 2 * mg) // n for i in range(n + 1)],
    )


def is_dark_cell(gray, y0, y1, x0, x1, pad=4):
    inner = gray[y0 + pad:y1 - pad, x0 + pad:x1 - pad]
    return inner.size == 0 or float(np.mean(inner)) < 160


def ocr_number(gray, y0, y1, x0, x1, pad=3):
    """Read the small number from the top-left corner of a white cell."""
    ch = y1 - y0 - 2 * pad
    cw = x1 - x0 - 2 * pad
    if ch <= 0 or cw <= 0:
        return None

    roi = gray[
        y0 + pad: y0 + pad + max(1, int(ch * 0.48)),
        x0 + pad: x0 + pad + max(1, int(cw * 0.58)),
    ]
    if roi.size == 0:
        return None

    scale = max(3, 80 // min(roi.shape))
    big = cv2.resize(roi, (roi.shape[1] * scale, roi.shape[0] * scale),
                     interpolation=cv2.INTER_CUBIC)
    _, thresh = cv2.threshold(big, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    padded = cv2.copyMakeBorder(thresh, 10, 10, 10, 10,
                                cv2.BORDER_CONSTANT, value=255)

    for psm in (7, 8, 6):
        txt = pytesseract.image_to_string(
            padded,
            config=f'--psm {psm} --oem 3 -c tessedit_char_whitelist=0123456789',
        ).strip()
        for m in re.findall(r'\d+', txt):
            n = int(m)
            if 1 <= n <= 26:
                return n
    return None


def analyze_image(image_bytes):
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError('Cannot decode image — please upload a valid PNG or JPG.')
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    hl, vl = find_grid_lines(gray)
    n_rows, n_cols = len(hl) - 1, len(vl) - 1

    freq = Counter()
    grid = []
    for r in range(n_rows):
        row = []
        y0, y1 = hl[r], hl[r + 1]
        for c in range(n_cols):
            x0, x1 = vl[c], vl[c + 1]
            if is_dark_cell(gray, y0, y1, x0, x1):
                row.append({'type': 'dark', 'number': None})
            else:
                num = ocr_number(gray, y0, y1, x0, x1)
                if num:
                    freq[num] += 1
                row.append({'type': 'light', 'number': num})
        grid.append(row)

    return grid, freq, n_rows, n_cols


def render_grid(grid, n_rows, n_cols, cell=44):
    b = 1
    im = Image.new('RGB', (n_cols * cell + b, n_rows * cell + b), '#222222')
    draw = ImageDraw.Draw(im)
    font = _load_font(13)

    for r, row in enumerate(grid):
        for c, cd in enumerate(row):
            x, y = c * cell + b, r * cell + b
            if cd['type'] == 'dark':
                draw.rectangle([x, y, x + cell - b, y + cell - b], fill='#555555')
            else:
                draw.rectangle([x, y, x + cell - b, y + cell - b], fill='white')
                num = cd['number']
                if num is not None:
                    draw.text((x + 3, y + 2), str(num), fill='#1a237e', font=font)
                else:
                    draw.text((x + 3, y + 2), '?', fill='#cc0000', font=font)

    buf = io.BytesIO()
    im.save(buf, 'PNG')
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode('utf-8')


@app.route('/')
def index():
    return render_template('codeword.html')


@app.route('/analyze', methods=['POST'])
def analyze():
    if 'image' not in request.files or not request.files['image'].filename:
        return jsonify({'error': 'No image uploaded'}), 400
    try:
        image_bytes = request.files['image'].read()
        grid, freq, n_rows, n_cols = analyze_image(image_bytes)
        grid_b64 = render_grid(grid, n_rows, n_cols)

        total = sum(freq.values())
        freq_list = []
        for rank, (num, count) in enumerate(sorted(freq.items(), key=lambda x: -x[1])):
            freq_list.append({
                'number': num,
                'count': count,
                'percentage': round(100 * count / total, 1) if total else 0,
                'letter_hint': ENGLISH_FREQ_ORDER[rank] if rank < 26 else '?',
            })

        return jsonify({
            'grid_image': grid_b64,
            'frequency': freq_list,
            'stats': {
                'n_rows': n_rows,
                'n_cols': n_cols,
                'total_active': total,
                'numbers_found': len(freq),
            },
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
