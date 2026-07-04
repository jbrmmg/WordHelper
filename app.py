import sqlite3

from flask import Flask, render_template, request, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_prefix=1)

WORD_LENGTH = 5
DB_PATH = "/var/lib/wordhelper/words.db"


def load_words():
    con = sqlite3.connect(DB_PATH)

    rows = con.execute(
        "SELECT word FROM words WHERE length = ? AND is_proper = 0 AND has_special = 0 AND is_ascii = 1",
        (WORD_LENGTH,)
    ).fetchall()
    words = [row[0].upper() for row in rows]

    con.close()

    freq = {}
    for word in words:
        for ch in word:
            freq[ch] = freq.get(ch, 0) + 1
    letter_order = sorted(freq, key=lambda c: -freq[c])

    return words, letter_order


words, letter_order = load_words()


def check_word(word, excluded, pattern, must_include, exclude_patterns):
    if len(word) != WORD_LENGTH:
        return False

    for ch in excluded:
        if ch in word:
            return False

    for i, p in enumerate(pattern):
        if p != '_' and p != word[i]:
            return False

    for ch in must_include:
        if ch not in word:
            return False

    for ep in exclude_patterns:
        for i, p in enumerate(ep):
            if p != '_' and p == word[i]:
                return False

    return True


@app.route('/')
def index():
    return render_template('index.html', letter_order=letter_order, words=words)


@app.route('/evaluate', methods=['POST'])
def evaluate():
    data = request.json
    letter_states = data.get('letters', {})

    unused = []
    must_include = []
    pattern = ['_'] * WORD_LENGTH
    exclude_patterns = []

    for letter in letter_order:
        state = letter_states.get(letter, {})
        enabled = state.get('enabled', True)
        in_word = state.get('inWord', False)
        include_pos = state.get('includePos', [False] * WORD_LENGTH)
        exclude_pos = state.get('excludePos', [False] * WORD_LENGTH)

        if not enabled:
            unused.append(letter)
            continue

        if in_word or any(exclude_pos):
            must_include.append(letter)

        for pos, val in enumerate(include_pos):
            if val:
                pattern[pos] = letter

        if any(exclude_pos):
            exclude_patterns.append([letter if p else '_' for p in exclude_pos])

    matching = [w for w in words if check_word(w, unused, pattern, must_include, exclude_patterns)]

    return jsonify({
        'words': matching,
        'count': len(matching),
        'excluded': ''.join(unused),
        'mustInclude': ''.join(must_include),
        'pattern': ''.join(pattern),
    })


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
