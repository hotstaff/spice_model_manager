from flask import Flask
from models import init_db
from views import main_bp

app = Flask(__name__)

# データベースの初期化
init_db()

# Blueprintの登録
app.register_blueprint(main_bp)

@app.route('/')
def home():
    return "Welcome to the Spice Model Manager API!"

if __name__ == '__main__':
    app.run()
