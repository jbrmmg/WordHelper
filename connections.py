from flask import Flask, render_template
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_prefix=1)


@app.route('/')
def index():
    return render_template('connections.html')


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)
