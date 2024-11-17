import os
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
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
        conn.commit()  # 明示的にコミット

# データを取得する関数 (全データ取得)
def get_all_data():
    engine = get_db_connection()
    query = "SELECT * FROM data"
    query = text(query)  # クエリを text() でラップ
    df = pd.read_sql(query, engine)
    return df

# 特定の条件でデータを検索する関数
def search_data(device_name=None, device_type=None, spice_string=None):
    engine = get_db_connection()
    
    # 動的なクエリを構築するためのリスト
    query = "SELECT * FROM data WHERE true"  # WHERE trueは常に真になるため、追加条件がある場合に便利
    params = {}
    
    if device_name:
        query += " AND device_name ILIKE :device_name"
        params["device_name"] = f"%{device_name}%"
    if device_type:
        query += " AND device_type ILIKE :device_type"
        params["device_type"] = f"%{device_type}%"
    if spice_string:
        query += " AND spice_string ILIKE :spice_string"
        params["spice_string"] = f"%{spice_string}%"
    
    # 構築されたクエリを実行
    query = text(query)  # クエリを text() でラップ
    df = pd.read_sql(query, engine, params=params)
    return df

def get_data_by_id(data_id):
    engine = get_db_connection()
    query = "SELECT * FROM data WHERE id = :data_id"
    query = text(query)  # クエリを text() でラップ
    
    # パラメータを辞書として渡す
    df = pd.read_sql(query, engine, params={"data_id": data_id})
    return df

# データを新規追加する関数
def add_data(device_name, device_type, spice_string):
    engine = get_db_connection()
    
    with engine.connect() as conn:
        # デバイス名が既に存在するか確認する
        result = conn.execute(text("""
            SELECT COUNT(*) FROM data WHERE device_name = :device_name
        """), {"device_name": device_name}).fetchone()

        if result[0] > 0:
            # 既に同じデバイス名が存在する場合はFalseを返す
            return False
        
        try:
            # 新しいデバイスを追加
            conn.execute(text("""
                INSERT INTO data (device_name, device_type, spice_string)
                VALUES (:device_name, :device_type, :spice_string)
            """), {"device_name": device_name, "device_type": device_type, "spice_string": spice_string})
            conn.commit()  # 明示的にコミット
            return True  # 成功した場合はTrueを返す
        except IntegrityError:
            # 重複などのエラーが発生した場合はロールバック
            conn.rollback()
            return False

# データを更新する関数
def update_data(data_id, device_name=None, device_type=None, spice_string=None):
    engine = get_db_connection()
    with engine.connect() as conn:
        # データが存在するか確認
        result = conn.execute(text("SELECT * FROM data WHERE id = :data_id"), {"data_id": data_id}).fetchone()
        if result is None:
            # データが存在しない場合はFalseを返す
            return False
        
        # データを更新
        conn.execute(text("""
            UPDATE data
            SET device_name = COALESCE(:device_name, device_name),
                device_type = COALESCE(:device_type, device_type),
                spice_string = COALESCE(:spice_string, spice_string)
            WHERE id = :data_id
        """), {"device_name": device_name, "device_type": device_type, "spice_string": spice_string, "data_id": data_id})
        conn.commit()  # 明示的にコミット
    return True  # 更新成功

# データを削除する関数
def delete_data(data_id):
    engine = get_db_connection()
    with engine.connect() as conn:
        # データが存在するか確認
        result = conn.execute(text("SELECT * FROM data WHERE id = :data_id"), {"data_id": data_id}).fetchone()
        if result is None:
            return False  # データが存在しない場合
        
        conn.execute(text("DELETE FROM data WHERE id = :data_id"), {"data_id": data_id})
        conn.commit()  # 明示的にコミット
    return True  # 削除成功

## imageデータベース用のコード
def save_image_to_db(data_id, image_file, image_type, image_format):
    engine = get_db_connection()
    with engine.connect() as conn:
        # 画像ファイルをバイナリとして読み込む
        image_data = image_file.read()

        # image_type と data_id が重複している場合、更新する
        result = conn.execute(text("""
            SELECT 1 FROM simulation_images WHERE data_id = :data_id AND image_type = :image_type
        """), {"data_id": data_id, "image_type": image_type}).fetchone()

        if result:
            # 既存のレコードがあれば更新
            conn.execute(text("""
                UPDATE simulation_images 
                SET image_format = :image_format, image_data = :image_data 
                WHERE data_id = :data_id AND image_type = :image_type
            """), {"image_format": image_format, "image_data": image_data, "data_id": data_id, "image_type": image_type})
        else:
            # レコードがなければ新しく挿入
            conn.execute(text("""
                INSERT INTO simulation_images (data_id, image_type, image_format, image_data)
                VALUES (:data_id, :image_type, :image_format, :image_data)
            """), {"data_id": data_id, "image_type": image_type, "image_format": image_format, "image_data": image_data})
        conn.commit()  # 明示的にコミット

def delete_image_from_db(data_id, image_type=None):
    """指定された data_id に関連する画像を削除（image_typeが指定されない場合は全て削除）"""
    engine = get_db_connection()
    with engine.connect() as conn:
        # image_type が指定されていない場合、data_id に関連する全ての画像を削除
        if image_type:
            conn.execute(text("""
                DELETE FROM simulation_images 
                WHERE data_id = :data_id AND image_type = :image_type
            """), {"data_id": data_id, "image_type": image_type})
        else:
            conn.execute(text("""
                DELETE FROM simulation_images 
                WHERE data_id = :data_id
            """), {"data_id": data_id})
        conn.commit()  # 明示的にコミット

def get_image_from_db(data_id, image_type=None):
    """指定された data_id と image_type に基づいてデータベースから画像データを取得します。"""
    engine = get_db_connection()
    with engine.connect() as conn:
        # image_type が指定されている場合は、条件を追加してクエリを実行
        if image_type:
            result = conn.execute(text("""
                SELECT image_data, image_format, image_type 
                FROM simulation_images 
                WHERE data_id = :data_id AND image_type = :image_type
            """), {"data_id": data_id, "image_type": image_type}).fetchone()
        else:
            result = conn.execute(text("""
                SELECT image_data, image_format, image_type 
                FROM simulation_images 
                WHERE data_id = :data_id
            """), {"data_id": data_id}).fetchone()

    if result is None:
        return None

    # 画像データとメタデータを抽出
    image_data, image_format, image_type = result

    # バイナリデータを BytesIO オブジェクトに変換
    image_io = BytesIO(image_data)

    return image_io, image_format, image_type
