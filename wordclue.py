import sqlite3
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
DB_PATH = "/var/lib/wordhelper/words.db"


@app.route('/')
def index():
    return render_template('wordclue.html')


@app.route('/search', methods=['POST'])
def search():
    data      = request.json
    length    = int(data.get('length', 5))
    pattern   = data.get('pattern', {})      # {"0": "a", "2": "t"}
    excluded  = [c.lower() for c in data.get('excluded', [])]
    must_have = [c.lower() for c in data.get('mustHave', [])]
    groups    = data.get('groups', [])        # [[0, 3], [1, 4], ...]

    con = sqlite3.connect(DB_PATH)
    rows = con.execute(
        "SELECT word FROM words "
        "WHERE length=? AND is_proper=0 AND has_special=0 AND is_ascii=1",
        (length,)
    ).fetchall()
    con.close()

    results = []
    for (word,) in rows:
        w = word.lower()

        if any(c in w for c in excluded):
            continue
        if any(c not in w for c in must_have):
            continue

        ok = True
        for pos_str, letter in pattern.items():
            if w[int(pos_str)] != letter.lower():
                ok = False
                break
        if not ok:
            continue

        for group in groups:
            if len(set(w[p] for p in group)) > 1:
                ok = False
                break
        if not ok:
            continue

        results.append(w.upper())

    return jsonify({'words': results, 'count': len(results)})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
