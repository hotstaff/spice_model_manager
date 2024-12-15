import os
from flask import Flask
from simulation.endpoints import simulation 

app = Flask(__name__)

app.secret_key = os.getenv('FLASK_SECRET_KEY', os.urandom(24))

# APIエンドポイントを設定
app.register_blueprint(simulation)

if __name__ == "__main__":
    app.run(debug=False, port=5000)
