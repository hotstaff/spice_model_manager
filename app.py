from flask import Flask
from models.db_model import init_db
from views import model_views  # views.pyからmodel_viewsをインポート

app = Flask(__name__)

# データベースの初期化
init_db()

# APIエンドポイントを設定
app.register_blueprint(model_views)

@app.route('/')
def home():
    return "Welcome to the Spice Model Manager API!"

if __name__ == '__main__':
    app.run()
