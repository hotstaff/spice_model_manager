import os
from sqlalchemy import create_engine
import pandas as pd
from dotenv import load_dotenv

# .envファイルを読み込む
load_dotenv()

# 環境変数から接続情報を取得
def get_db_connection():
    connection_string = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@" \
                        f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
    engine = create_engine(connection_string)
    return engine

# データベースの存在確認と作成
def create_db_if_not_exists():
    try:
        engine = get_db_connection()
        with engine.connect() as conn:
            conn.execute('SELECT 1')  # データベース接続のテスト
        print("データベースが存在します。")
    except Exception as e:
        print("データベースが存在しないため、作成します。")
        # データベースを作成する処理
        engine = create_engine(
            f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@" 
            f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/postgres"
        )
        with engine.connect() as conn:
            conn.execute(f"CREATE DATABASE {os.getenv('DB_NAME')}")

# テーブルの初期化
def init_db():
    create_db_if_not_exists()  # データベースの存在確認と作成
    engine = get_db_connection()
    with engine.connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS data (
                id SERIAL PRIMARY KEY,
                device_name TEXT,
                device_type TEXT,
                spice_string TEXT
            )
        """)

# データを取得する関数 (全データ取得)
def get_all_data():
    engine = get_db_connection()
    with engine.connect() as conn:
        df = pd.read_sql_query("SELECT * FROM data", conn)
    return df

# 特定の条件でデータを検索する関数
def search_data(device_name=None, device_type=None, spice_string=None):
    engine = get_db_connection()
    with engine.connect() as conn:
        query = "SELECT * FROM data WHERE true"
        params = []

        if device_name:
            query += " AND device_name ILIKE %s"
            params.append(f"%{device_name}%")
        if device_type:
            query += " AND device_type ILIKE %s"
            params.append(f"%{device_type}%")
        if spice_string:
            query += " AND spice_string ILIKE %s"
            params.append(f"%{spice_string}%")
        
        df = pd.read_sql_query(query, conn, params=params)
    return df

# 特定のIDのデータを取得する関数
def get_data_by_id(data_id):
    engine = get_db_connection()
    with engine.connect() as conn:
        df = pd.read_sql_query("SELECT * FROM data WHERE id = %s", conn, params=(data_id,))
    return df

# データを新規追加する関数
def add_data(device_name, device_type, spice_string):
    engine = get_db_connection()
    with engine.connect() as conn:
        conn.execute(
            "INSERT INTO data (device_name, device_type, spice_string) VALUES (%s, %s, %s)",
            (device_name, device_type, spice_string)
        )

# データを更新する関数
def update_data(data_id, device_name=None, device_type=None, spice_string=None):
    engine = get_db_connection()
    with engine.connect() as conn:
        result = conn.execute("SELECT * FROM data WHERE id = %s", (data_id,))
        if result.fetchone() is None:
            return False  # データが存在しない場合
        conn.execute("""
            UPDATE data
            SET device_name = COALESCE(%s, device_name),
                device_type = COALESCE(%s, device_type),
                spice_string = COALESCE(%s, spice_string)
            WHERE id = %s
        """, (device_name, device_type, spice_string, data_id))
    return True  # 更新成功

# データを削除する関数
def delete_data(data_id):
    engine = get_db_connection()
    with engine.connect() as conn:
        result = conn.execute("SELECT * FROM data WHERE id = %s", (data_id,))
        if result.fetchone() is None:
            return False  # データが存在しない場合
        conn.execute("DELETE FROM data WHERE id = %s", (data_id,))
    return True  # 削除成功
