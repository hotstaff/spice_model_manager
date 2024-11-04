from flask import Blueprint, render_template
from models import get_all_data, get_data_by_id

main_bp = Blueprint('main', __name__)

# モデル一覧を表示するビュー
@main_bp.route('/models')
def show_models():
    df = get_all_data()
    return render_template('model_list.html', models=df.to_dict(orient='records'))

# モデルの詳細を表示するビュー
@main_bp.route('/models/<int:model_id>')
def show_model(model_id):
    df = get_data_by_id(model_id)
    if df.empty:
        return "Model not found", 404
    model = df.to_dict(orient='records')[0]
    return render_template('model_detail.html', model=model)
