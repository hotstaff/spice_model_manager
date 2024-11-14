from flask import Flask, redirect, url_for
from models.db_model import init_db
from views import model_views  # views.pyからmodel_viewsをインポート

app = Flask(__name__)

# データベースの初期化
init_db()

# APIエンドポイントを設定
app.register_blueprint(model_views)

@app.route('/')
def home():
    # /models にリダイレクト
    return redirect(url_for('model_views.models'))  # model_views.blueprint内で/modelsのビュー関数が定義されていることを前提

if __name__ == '__main__':
    app.run()
