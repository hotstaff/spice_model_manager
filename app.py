from flask import Flask, request, jsonify, abort
import pandas as pd
import sqlite3

app = Flask(__name__)

# SQLiteへの接続を設定
conn = sqlite3.connect("data.db", check_same_thread=False)
cursor = conn.cursor()

# テーブルの初期化 (ID列を追加)
cursor.execute("""
CREATE TABLE IF NOT EXISTS data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    column1 TEXT,
    column2 TEXT
)
""")
conn.commit()

@app.route('/')
def home():
    return "Welcome to the Spice Model Manager API!"

# データを取得するAPI (全データ取得)
@app.route('/data', methods=['GET'])
def get_data():
    df = pd.read_sql("SELECT * FROM data", conn)
    return jsonify(df.to_dict(orient="records"))

# 特定のIDのデータを取得するAPI
@app.route('/data/<int:data_id>', methods=['GET'])
def get_data_by_id(data_id):
    df = pd.read_sql("SELECT * FROM data WHERE id = ?", conn, params=(data_id,))
    if df.empty:
        return abort(404, description="Data not found")
    return jsonify(df.to_dict(orient="records")[0])

# データを新規追加するAPI
@app.route('/data', methods=['POST'])
def add_data():
    if not request.json or 'column1' not in request.json or 'column2' not in request.json:
        return abort(400, description="Invalid data")
    
    column1 = request.json['column1']
    column2 = request.json['column2']
    
    cursor.execute("INSERT INTO data (column1, column2) VALUES (?, ?)", (column1, column2))
    conn.commit()
    return "Data added successfully", 201

# データを更新するAPI
@app.route('/data/<int:data_id>', methods=['PUT'])
def update_data(data_id):
    if not request.json:
        return abort(400, description="Invalid data")
    
    column1 = request.json.get('column1')
    column2 = request.json.get('column2')
    
    # 更新対象が存在するか確認
    cursor.execute("SELECT * FROM data WHERE id = ?", (data_id,))
    if cursor.fetchone() is None:
        return abort(404, description="Data not found")
    
    cursor.execute("""
        UPDATE data
        SET column1 = COALESCE(?, column1),
            column2 = COALESCE(?, column2)
        WHERE id = ?
    """, (column1, column2, data_id))
    conn.commit()
    return "Data updated successfully", 200

# データを削除するAPI
@app.route('/data/<int:data_id>', methods=['DELETE'])
def delete_data(data_id):
    cursor.execute("SELECT * FROM data WHERE id = ?", (data_id,))
    if cursor.fetchone() is None:
        return abort(404, description="Data not found")
    
    cursor.execute("DELETE FROM data WHERE id = ?", (data_id,))
    conn.commit()
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

