import os
from sqlalchemy import create_engine, text
import pandas as pd
from dotenv import load_dotenv
from io import BytesIO

# .envファイルを読み込む
load_dotenv()

# 環境変数から接続情報を取得
def get_db_connection():
    # 環境変数からDB接続URLを取得
    engine = create_engine(os.getenv("DB_URL"))
    return engine

# データベースに再接続してテーブルを作成
def init_db():
    create_db_if_not_exists()  # データベースの存在確認と作成

    # データベースに再接続してテーブルを作成
    engine = get_db_connection()
    with engine.connect() as conn:
        # text() を使ってクエリをラップ
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS data (
            id SERIAL PRIMARY KEY,
            device_name TEXT,
            device_type TEXT,
            spice_string TEXT
        )
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS simulation_images (
            id SERIAL PRIMARY KEY,
            data_id INT REFERENCES data(id) ON DELETE CASCADE,
            image_type TEXT,
            image_format TEXT,
            image_data BYTEA
        )
        """))

# データを取得する関数 (全データ取得)
def get_all_data():
    engine = get_db_connection()
    query = "SELECT * FROM data"
    df = pd.read_sql(query, engine)
    return df

# 特定の条件でデータを検索する関数
def search_data(device_name=None, device_type=None, spice_string=None):
    engine = get_db_connection()
    
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
    df = pd.read_sql(query, engine, params=params)
    return df

# 特定のIDのデータを取得する関数
def get_data_by_id(data_id):
    engine = get_db_connection()
    query = "SELECT * FROM data WHERE id = %s"
    df = pd.read_sql(query, engine, params=(data_id,))
    return df

# データを新規追加する関数
def add_data(device_name, device_type, spice_string):
    engine = get_db_connection()
    with engine.connect() as conn:
        conn.execute("""
            INSERT INTO data (device_name, device_type, spice_string)
            VALUES (%s, %s, %s)
        """, (device_name, device_type, spice_string))

# データを更新する関数
def update_data(data_id, device_name=None, device_type=None, spice_string=None):
    engine = get_db_connection()
    with engine.connect() as conn:
        # データが存在するか確認
        result = conn.execute("SELECT * FROM data WHERE id = %s", (data_id,)).fetchone()
        if result is None:
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
        # データが存在するか確認
        result = conn.execute("SELECT * FROM data WHERE id = %s", (data_id,)).fetchone()
        if result is None:
            return False  # データが存在しない場合
        
        conn.execute("DELETE FROM data WHERE id = %s", (data_id,))
    return True  # 削除成功

## imageデータベース用のコード
def save_image_to_db(data_id, image_file, image_type, image_format):
    engine = get_db_connection()
    with engine.connect() as conn:
        # 画像ファイルをバイナリとして読み込む
        image_data = image_file.read()

        # image_type と data_id が重複している場合、更新する
        result = conn.execute("""
            SELECT 1 FROM simulation_images WHERE data_id = %s AND image_type = %s
        """, (data_id, image_type)).fetchone()

        if result:
            # 既存のレコードがあれば更新
            conn.execute("""
                UPDATE simulation_images 
                SET image_format = %s, image_data = %s 
                WHERE data_id = %s AND image_type = %s
            """, (image_format, image_data, data_id, image_type))
        else:
            # レコードがなければ新しく挿入
            conn.execute("""
                INSERT INTO simulation_images (data_id, image_type, image_format, image_data)
                VALUES (%s, %s, %s, %s)
            """, (data_id, image_type, image_format, image_data))

def delete_image_from_db(data_id, image_type=None):
    """指定された data_id に関連する画像を削除（image_typeが指定されない場合は全て削除）"""
    engine = get_db_connection()
    with engine.connect() as conn:
        # image_type が指定されていない場合、data_id に関連する全ての画像を削除
        if image_type:
            conn.execute("""
                DELETE FROM simulation_images 
                WHERE data_id = %s AND image_type = %s
            """, (data_id, image_type))
        else:
            conn.execute("""
                DELETE FROM simulation_images 
                WHERE data_id = %s
            """, (data_id,))

def get_image_from_db(data_id, image_type=None):
    """指定された data_id と image_type に基づいてデータベースから画像データを取得します。"""
    engine = get_db_connection()
    with engine.connect() as conn:
        # image_type が指定されている場合は、条件を追加してクエリを実行
        if image_type:
            result = conn.execute("""
                SELECT image_data, image_format, image_type 
                FROM simulation_images 
                WHERE data_id = %s AND image_type = %s
            """, (data_id, image_type)).fetchone()
        else:
            result = conn.execute("""
                SELECT image_data, image_format, image_type 
                FROM simulation_images 
                WHERE data_id = %s
            """, (data_id,)).fetchone()

    if result is None:
        return None

    # 画像データとメタデータを抽出
    image_data, image_format, image_type = result

    # バイナリデータを BytesIO オブジェクトに変換
    image_io = BytesIO(image_data)

    return image_io, image_format, image_type
