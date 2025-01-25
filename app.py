import os
from dotenv import load_dotenv

from flask import Flask, redirect, url_for, jsonify, render_template
from models.db_model import init_db, migrate_db
from views import model_views  # views.pyからmodel_viewsをインポート
from simulation_views import simu_views

# dotenv
load_dotenv()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB

app.secret_key = os.getenv('FLASK_SECRET_KEY', os.urandom(24))

# データベースの初期化
init_db()
# migrate_db()

# APIエンドポイントを設定
app.register_blueprint(model_views)
app.register_blueprint(simu_views)

@app.route('/')
def home():
    # model_views.list_modelsが正しいエンドポイント名
    return redirect(url_for('model_views.get_models_web'))

@app.route('/sitemap')
def sitemap():
    links = []
    for rule in app.url_map.iter_rules():
        if rule.endpoint != 'static':  # Exclude static files
            url = {
                'endpoint': rule.endpoint,
                'methods': list(rule.methods),
                'url': str(rule)
            }
            links.append(url)
    return render_template('sitemap.html', links=links)

if __name__ == '__main__':
    app.run()
