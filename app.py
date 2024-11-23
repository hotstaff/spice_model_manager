import os
from flask import Flask, redirect, url_for
from models.db_model import init_db, migrate_db_with_defaults
from views import model_views  # views.pyからmodel_viewsをインポート

app = Flask(__name__)

app.secret_key = os.getenv('FLASK_SECRET_KEY', os.urandom(24))

# データベースの初期化
init_db()
migrate_db_with_defaults()

# APIエンドポイントを設定
app.register_blueprint(model_views)

@app.route('/')
def home():
    # model_views.list_modelsが正しいエンドポイント名
    return redirect(url_for('model_views.list_models'))

if __name__ == '__main__':
    app.run()
