import sqlite3
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
DB_PATH = "/var/lib/wordhelper/words.db"

COMMON_LETTERS   = set('etaoinshrdlcu')
UNCOMMON_LETTERS = set('mwfgypbvkjxqz')


@app.route('/')
def index():
    return render_template('wordclue.html')


@app.route('/search', methods=['POST'])
def search():
    data          = request.json
    length        = int(data.get('length', 5))
    pattern       = data.get('pattern', {})      # {"0": "a", "2": "t"}
    excluded      = [c.lower() for c in data.get('excluded', [])]
    must_have     = [c.lower() for c in data.get('mustHave', [])]
    common_req    = [c.lower() for c in data.get('commonLetters', [])]
    uncommon_req  = [c.lower() for c in data.get('uncommonLetters', [])]
    pos_common    = [int(p) for p in data.get('posCommon', [])]
    pos_uncommon  = [int(p) for p in data.get('posUncommon', [])]
    groups        = data.get('groups', [])        # [[0, 3], [1, 4], ...]

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

        # A letter placed at specific positions may not appear anywhere else
        pattern_allowed = {}
        for pos_str, letter in pattern.items():
            ltr = letter.lower()
            if ltr not in pattern_allowed:
                pattern_allowed[ltr] = set()
            pattern_allowed[ltr].add(int(pos_str))
        for ltr, allowed in pattern_allowed.items():
            for i, c in enumerate(w):
                if c == ltr and i not in allowed:
                    ok = False
                    break
            if not ok:
                break
        if not ok:
            continue

        for ltr in common_req:
            if ltr not in w or ltr not in COMMON_LETTERS:
                ok = False
                break
        if not ok:
            continue

        for ltr in uncommon_req:
            if ltr not in w or ltr not in UNCOMMON_LETTERS:
                ok = False
                break
        if not ok:
            continue

        for pos in pos_common:
            if pos < len(w) and w[pos] not in COMMON_LETTERS:
                ok = False
                break
        if not ok:
            continue

        for pos in pos_uncommon:
            if pos < len(w) and w[pos] not in UNCOMMON_LETTERS:
                ok = False
                break
        if not ok:
            continue

        for group in groups:
            group_set = set(group)
            letters_in_group = set(w[p] for p in group)
            if len(letters_in_group) > 1:
                ok = False
                break
            group_letter = next(iter(letters_in_group))
            if any(c == group_letter for i, c in enumerate(w) if i not in group_set):
                ok = False
                break
        if not ok:
            continue

        results.append(w.upper())

    return jsonify({'words': results, 'count': len(results)})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
