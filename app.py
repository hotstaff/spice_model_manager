from flask import Flask, request, jsonify, abort
from models.db_model import get_all_data, get_data_by_id, add_data, update_data, delete_data, init_db

app = Flask(__name__)

# データベースの初期化
init_db()

@app.route('/')
def home():
    return "Welcome to the Spice Model Manager API!"

# データを取得するAPI (全データ取得)
@app.route('/data', methods=['GET'])
def get_data():
    df = get_all_data()
    return jsonify(df.to_dict(orient="records"))

# 特定のIDのデータを取得するAPI
@app.route('/data/<int:data_id>', methods=['GET'])
def get_data_by_id_endpoint(data_id):
    df = get_data_by_id(data_id)
    if df.empty:
        return abort(404, description="Data not found")
    return jsonify(df.to_dict(orient="records")[0])

# データを新規追加するAPI
@app.route('/data', methods=['POST'])
def add_data_endpoint():
    if not request.json or 'column1' not in request.json or 'column2' not in request.json:
        return abort(400, description="Invalid data")
    
    column1 = request.json['column1']
    column2 = request.json['column2']
    
    add_data(column1, column2)
    return "Data added successfully", 201

# データを更新するAPI
@app.route('/data/<int:data_id>', methods=['PUT'])
def update_data_endpoint(data_id):
    if not request.json:
        return abort(400, description="Invalid data")
    
    column1 = request.json.get('column1')
    column2 = request.json.get('column2')
    
    if not update_data(data_id, column1, column2):
        return abort(404, description="Data not found")
    
    return "Data updated successfully", 200

# データを削除するAPI
@app.route('/data/<int:data_id>', methods=['DELETE'])
def delete_data_endpoint(data_id):
    if not delete_data(data_id):
        return abort(404, description="Data not found")
    
    return "Data deleted successfully", 200

# エラーハンドリング
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": str(error)}), 404

@app.errorhandler(400)
def bad_request(error):
    return jsonify({"error": str(error)}), 400

if __name__ == '__main__':
    app.run()
