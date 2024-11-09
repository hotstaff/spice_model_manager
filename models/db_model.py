import os
import psycopg2
import pandas as pd
from dotenv import load_dotenv

# .envファイルを読み込む
load_dotenv()

# 環境変数から接続情報を取得
def get_db_connection():
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )
    return conn

# データベースの存在確認と作成
def create_db_if_not_exists():
    try:
        # まず、指定されたデータベースに接続を試みる
        conn = get_db_connection()
        conn.close()
        print("データベースが存在します。")
    except psycopg2.OperationalError as e:
        # データベースが存在しない場合
        print("データベースが存在しないため、作成します。")
        # データベースを作成する処理
        conn = psycopg2.connect(
            dbname="postgres",  # PostgreSQLのデフォルトのデータベース
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT")
        )
        conn.autocommit = True
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE {os.getenv('DB_NAME')}")
        conn.close()

# テーブルの初期化
def init_db():
    create_db_if_not_exists()  # データベースの存在確認と作成

    # データベースに再接続してテーブルを作成
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS data (
        id SERIAL PRIMARY KEY,
        device_name TEXT,
        device_type TEXT,
        spice_string TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS simulation_images (
        id SERIAL PRIMARY KEY,
        data_id INT REFERENCES data(id) ON DELETE CASCADE,
        image_type TEXT,
        image_path TEXT
    )
    """)


    conn.commit()
    conn.close()

# データを取得する関数 (全データ取得)
def get_all_data():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM data", conn)
    conn.close()
    return df

# 特定の条件でデータを検索する関数
def search_data(device_name=None, device_type=None, spice_string=None):
    conn = get_db_connection()
    
    # 動的なクエリを構築するためのリスト
    query = "SELECT * FROM data WHERE true"  # WHERE trueは常に真になるため、追加条件がある場合に便利
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
    
    # 構築されたクエリを実行
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

# 特定のIDのデータを取得する関数
def get_data_by_id(data_id):
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM data WHERE id = %s", conn, params=(data_id,))
    conn.close()
    return df

# データを新規追加する関数
def add_data(device_name, device_type, spice_string):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO data (device_name, device_type, spice_string) VALUES (%s, %s, %s)",
        (device_name, device_type, spice_string)
    )
    conn.commit()
    conn.close()

# データを更新する関数
def update_data(data_id, device_name=None, device_type=None, spice_string=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # データが存在するか確認
    cursor.execute("SELECT * FROM data WHERE id = %s", (data_id,))
    if cursor.fetchone() is None:
        conn.close()
        return False  # データが存在しない場合
    
    cursor.execute("""
        UPDATE data
        SET device_name = COALESCE(%s, device_name),
            device_type = COALESCE(%s, device_type),
            spice_string = COALESCE(%s, spice_string)
        WHERE id = %s
    """, (device_name, device_type, spice_string, data_id))
    conn.commit()
    conn.close()
    return True  # 更新成功

# データを削除する関数
def delete_data(data_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # データが存在するか確認
    cursor.execute("SELECT * FROM data WHERE id = %s", (data_id,))
    if cursor.fetchone() is None:
        conn.close()
        return False  # データが存在しない場合
    
    cursor.execute("DELETE FROM data WHERE id = %s", (data_id,))
    conn.commit()
    conn.close()
    return True  # 削除成功

## imageデーターベース用のコード

# 画像のURLをデータベースに追加する関数
def add_simulation_image(data_id, image_type, image_path):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO simulation_images (data_id, image_type, image_path) VALUES (%s, %s, %s)",
        (data_id, image_type, image_path)
    )
    conn.commit()
    conn.close()

# 特定のIDに関連する画像URLを取得する関数
def get_simulation_images_by_data_id(data_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT image_type, image_path FROM simulation_images WHERE data_id = %s", (data_id,))
    images = cursor.fetchall()
    conn.close()
    
    # 結果をリスト形式で返す
    return [{"image_type": image[0], "image_path": image[1]} for image in images]
