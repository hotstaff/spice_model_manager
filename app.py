from flask import Flask, request, jsonify, abort
from models.db_model import get_all_data, get_data_by_id, add_data, update_data, delete_data, init_db

app = Flask(__name__)

# データベースの初期化
init_db()

@app.route('/')
def home():
    return "Welcome to the Spice Model Manager API!"

# 全モデルデータを取得するAPI
@app.route('/api/models', methods=['GET'])
def get_models():
    df = get_all_data()
    return jsonify(df.to_dict(orient="records"))

# 特定のIDのモデルデータを取得するAPI
@app.route('/api/models/<int:model_id>', methods=['GET'])
def get_model_by_id(model_id):
    df = get_data_by_id(model_id)
    if df.empty:
        return abort(404, description="Model not found")
    return jsonify(df.to_dict(orient="records")[0])

# データを新規追加するAPI
@app.route('/api/models', methods=['POST'])
def add_model():
    if not request.json or 'column1' not in request.json or 'column2' not in request.json:
        return abort(400, description="Invalid data")
    
    column1 = request.json['column1']
    column2 = request.json['column2']
    
    add_data(column1, column2)
    return "Model added successfully", 201

# データを更新するAPI
@app.route('/api/models/<int:model_id>', methods=['PUT'])
def update_model(model_id):
    if not request.json:
        return abort(400, description="Invalid data")
    
    column1 = request.json.get('column1')
    column2 = request.json.get('column2')
    
    if not update_data(model_id, column1, column2):
        return abort(404, description="Model not found")
    
    return "Model updated successfully", 200

# データを削除するAPI
@app.route('/api/models/<int:model_id>', methods=['DELETE'])
def delete_model(model_id):
    if not delete_data(model_id):
        return abort(404, description="Model not found")
    
    return "Model deleted successfully", 200

# エラーハンドリング
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": str(error)}), 404

@app.errorhandler(400)
def bad_request(error):
    return jsonify({"error": str(error)}), 400

if __name__ == '__main__':
    app.run()
