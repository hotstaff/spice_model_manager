import os
from flask import Flask
from endpoints import simu

app = Flask(__name__)

app.secret_key = os.getenv('FLASK_SECRET_KEY', os.urandom(24))

# APIエンドポイントを設定
app.register_blueprint(simu)

if __name__ == "__main__":
    app.run(debug=False, port=5000)
