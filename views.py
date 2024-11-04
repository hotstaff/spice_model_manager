from flask import Blueprint, request, jsonify, abort, render_template
from models.db_model import get_all_data, get_data_by_id, add_data, update_data, delete_data

model_views = Blueprint('model_views', __name__)

# 全モデルデータを取得するAPI
@model_views.route('/api/models', methods=['GET'])
def get_models():
    df = get_all_data()
    return jsonify(df.to_dict(orient="records"))

# 特定のIDのモデルデータを取得するAPI
@model_views.route('/api/models/<int:model_id>', methods=['GET'])
def get_model_by_id(model_id):
    df = get_data_by_id(model_id)
    if df.empty:
        return abort(404, description="Model not found")
    return jsonify(df.to_dict(orient="records")[0])

# データを新規追加するAPI
@model_views.route('/api/models', methods=['POST'])
def add_model():
    if not request.json or 'column1' not in request.json or 'column2' not in request.json:
        return abort(400, description="Invalid data")
    
    column1 = request.json['column1']
    column2 = request.json['column2']
    
    add_data(column1, column2)
    return "Model added successfully", 201

# データを更新するAPI
@model_views.route('/api/models/<int:model_id>', methods=['PUT'])
def update_model(model_id):
    if not request.json:
        return abort(400, description="Invalid data")
    
    column1 = request.json.get('column1')
    column2 = request.json.get('column2')
    
    if not update_data(model_id, column1, column2):
        return abort(404, description="Model not found")
    
    return "Model updated successfully", 200

# データを削除するAPI
@model_views.route('/api/models/<int:model_id>', methods=['DELETE'])
def delete_model(model_id):
    if not delete_data(model_id):
        return abort(404, description="Model not found")
    
    return "Model deleted successfully", 200

# モデルの一覧をHTMLで表示
@model_views.route('/models', methods=['GET'])
def list_models():
    models = get_all_data()
    return render_template('index.html', models=models.to_dict(orient="records"))

# モデルの詳細をHTMLで表示
@model_views.route('/models/<int:model_id>', methods=['GET'])
def model_detail(model_id):
    model = get_data_by_id(model_id)
    if model.empty:
        return abort(404, description="Model not found")
    return render_template('model_detail.html', model=model.to_dict(orient="records")[0])

# エラーハンドリング
@model_views.errorhandler(404)
def not_found(error):
    return jsonify({"error": str(error)}), 404

@model_views.errorhandler(400)
def bad_request(error):
    return jsonify({"error": str(error)}), 400
