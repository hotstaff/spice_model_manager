import os
import json
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
            spice_string TEXT,
            author TEXT,
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            simulation_done BOOLEAN DEFAULT FALSE
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

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS basic_performance (
            id SERIAL PRIMARY KEY,
            data_id INT REFERENCES data(id) ON DELETE CASCADE,  -- dataテーブルと結合
            idss DOUBLE PRECISION,  -- Idss (Drain current) 浮動小数点型
            gm DOUBLE PRECISION,    -- Transconductance (Gm) 浮動小数点型
            cgs DOUBLE PRECISION,   -- Gate-Source capacitance (Cgs) 浮動小数点型
            cgd DOUBLE PRECISION,   -- Gate-Drain capacitance (Cgd) 浮動小数点型
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS experiment_data (
            id SERIAL PRIMARY KEY,  -- 測定データの一意のID
            data_id INTEGER REFERENCES data(id) ON DELETE CASCADE,  -- dataテーブルのIDを参照
            measurement_type TEXT DEFAULT 'General',  -- 測定種別（例: "IV Curve", "Frequency Response"）。デフォルトは 'General'
            data JSONB NOT NULL,  -- 測定データを格納するJSONBカラム（必須）
            operator_name TEXT DEFAULT 'Unknown',  -- 測定者の名前や識別子。デフォルトは 'Unknown'
            measurement_conditions JSONB DEFAULT '{}',  -- 測定条件をJSON形式で格納。デフォルトは空の辞書
            status TEXT DEFAULT 'raw',  -- 測定データの状態。デフォルトは 'raw'
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP  -- 測定データの登録日時
        )
        """))

        conn.commit()  # 明示的にコミット

def migrate_db():
    engine = get_db_connection()
    with engine.connect() as conn:
        # 'data' テーブルに simulation_done カラムを追加（デフォルト値を False に設定）
        conn.execute(text("""
        ALTER TABLE data
        ADD COLUMN IF NOT EXISTS simulation_done BOOLEAN DEFAULT FALSE
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
def add_data(device_name, device_type, spice_string, author="Anonymous", comment=""):
    engine = get_db_connection()

    with engine.connect() as conn:
        # デバイス名が既に存在するか確認する
        result = conn.execute(text("""
            SELECT COUNT(*) FROM data WHERE device_name = :device_name
        """), {"device_name": device_name}).fetchone()

        if result[0] > 0:
            # 既に同じデバイス名が存在する場合はNoneを返す
            return None
        
        try:
            # 新しいデバイスを追加
            result = conn.execute(text("""
                INSERT INTO data (device_name, device_type, spice_string, author, comment)
                VALUES (:device_name, :device_type, :spice_string, :author, :comment)
                RETURNING id
            """), {"device_name": device_name, "device_type": device_type, "spice_string": spice_string, "author": author, "comment": comment})
            # 追加したデバイスのIDを取得
            new_id = result.fetchone()[0]
            # コミットして変更を確定
            conn.commit()
            return new_id  # 追加したレコードのIDを返す
        except IntegrityError:
            # 重複などのエラーが発生した場合はロールバック
            conn.rollback()
            return None

# データを更新する関数
def update_data(data_id, device_name=None, device_type=None, spice_string=None, author="Anonymous", comment=""):
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
                spice_string = COALESCE(:spice_string, spice_string),
                author = COALESCE(:author, author),
                comment = COALESCE(:comment, comment)
            WHERE id = :data_id
        """), {"device_name": device_name, "device_type": device_type, "spice_string": spice_string, "author": author, "comment": comment, "data_id": data_id})
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

def update_simulation_done(data_id):
    """
    指定された data_id に対応するレコードの simulation_done を TRUE に更新します。

    :param data_id: 更新対象のデータID (dataテーブルのid)
    """
    engine = get_db_connection()
    with engine.connect() as conn:
        # simulation_done フィールドを TRUE に更新
        conn.execute(text("""
        UPDATE data
        SET simulation_done = TRUE
        WHERE id = :data_id
        """), {'data_id': data_id})
        
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


# basic_performanceテーブルのデータを追加・更新する関数
def update_basic_performance(data_id, idss=None, gm=None, cgs=None, cgd=None):
    engine = get_db_connection()
    with engine.connect() as conn:
        # data_idに対応するデータが存在するか確認
        result = conn.execute(text("SELECT * FROM basic_performance WHERE data_id = :data_id"), {"data_id": data_id}).fetchone()
        
        if result is None:
            # データが存在しない場合は新しく挿入
            conn.execute(text("""
                INSERT INTO basic_performance (data_id, idss, gm, cgs, cgd)
                VALUES (:data_id, :idss, :gm, :cgs, :cgd)
            """), {"data_id": data_id, "idss": idss, "gm": gm, "cgs": cgs, "cgd": cgd})
        else:
            # データが存在する場合は更新
            conn.execute(text("""
                UPDATE basic_performance
                SET idss = COALESCE(:idss, idss),
                    gm = COALESCE(:gm, gm),
                    cgs = COALESCE(:cgs, cgs),
                    cgd = COALESCE(:cgd, cgd)
                WHERE data_id = :data_id
            """), {"idss": idss, "gm": gm, "cgs": cgs, "cgd": cgd, "data_id": data_id})
        
        conn.commit()  # 明示的にコミット
    return True  # 更新または追加成功

def get_basic_performance_by_data_id(data_id):
    engine = get_db_connection()
    query = """
        SELECT * FROM basic_performance 
        WHERE data_id = :data_id
    """
    query = text(query)  # クエリを text() でラップ

    df = pd.read_sql(query, engine, params={"data_id": data_id})
    return df

def get_all_device_ids():
    query = "SELECT id FROM data"  # 'id' を取得
    engine = get_db_connection()  # データベース接続のエンジンを取得
    with engine.connect() as conn:  # with構文で接続を管理
        result = conn.execute(text(query))
        device_ids = [row[0] for row in result.fetchall()]  # idをリストとして取得
    return device_ids


# 測定データをexperiment_dataテーブルに追加する関数
def add_experiment_data(data_id, measurement_type, data_json, operator_name, measurement_conditions_json, status):
    # 実験データをデータベースに挿入する処理
    engine = get_db_connection()
    
    # data_json と measurement_conditions_json を JSON 文字列に変換
    data_json_str = json.dumps(data_json)  # 'data' を JSON 文字列に変換
    measurement_conditions_json_str = json.dumps(measurement_conditions_json)  # 'measurement_conditions' を JSON 文字列に変換
    
    query = """
        INSERT INTO experiment_data (data_id, measurement_type, data, operator_name, measurement_conditions, status)
        VALUES (%(data_id)s, %(measurement_type)s, %(data)s, %(operator_name)s, %(measurement_conditions)s, %(status)s)
        RETURNING id
    """
    params = {
        'data_id': data_id,
        'measurement_type': measurement_type,
        'data': data_json_str,  # ここで JSON 文字列を渡す
        'operator_name': operator_name,
        'measurement_conditions': measurement_conditions_json_str,  # ここで JSON 文字列を渡す
        'status': status
    }
    
    # クエリ実行
    result = engine.execute(query, params)
    new_id = result.fetchone()[0]
    return new_id

def get_experiment_data_by_data_id(data_id):
    """
    experiment_dataテーブルから指定されたdata_idに関連する実験データを取得し、Pandas DataFrameに変換する関数。

    Parameters:
        data_id (int): data_idに基づく実験データの取得

    Returns:
        pd.DataFrame: 実験データをPandas DataFrameに変換したもの
    """
    engine = get_db_connection()
    query = """
        SELECT id, measurement_type, data, operator_name, measurement_conditions, status, created_at
        FROM experiment_data
        WHERE data_id = :data_id
    """
    query = text(query)  # クエリを text() でラップ

    # クエリ結果をPandas DataFrameに変換
    df = pd.read_sql(query, engine, params={"data_id": data_id})

    return df