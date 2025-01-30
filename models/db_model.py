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
    engine = create_engine(
        os.getenv("DB_URL"),
        pool_size=10,  # 最大接続数
        max_overflow=5,  # 最大オーバーフロー数
        pool_timeout=30,  # タイムアウト時間
        pool_recycle=1800  # 接続の再利用時間
    )
    return engine

# データベースに再接続してテーブルを作成
def init_db():
    # データベースに再接続してテーブルを作成
    engine = get_db_connection()
    with engine.connect() as conn:
        # text() を使ってクエリをラップ
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS data (
            id SERIAL PRIMARY KEY,                          -- 一意のID
            device_name TEXT NOT NULL,                      -- デバイス名（必須）
            device_type TEXT NOT NULL,                      -- デバイスタイプ（必須）
            spice_string TEXT,                              -- SPICEモデルの文字列
            author TEXT DEFAULT 'Unknown',                 -- 作成者（デフォルト値あり）
            comment TEXT CHECK (LENGTH(comment) <= 500),   -- コメント（最大500文字）
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- 作成日時（デフォルト値あり）
            simulation_done BOOLEAN DEFAULT FALSE,         -- シミュレーションの完了フラグ
            CONSTRAINT unique_device UNIQUE (device_name, device_type) -- ユニーク制約
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
                gds DOUBLE PRECISION,   -- Drain-Source conductance (Gds) 浮動小数点型
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS experiment_data (
            id SERIAL PRIMARY KEY,                          -- 測定データの一意のID
            data_id INTEGER REFERENCES data(id) ON DELETE CASCADE, -- dataテーブルのIDを参照 (NULL許容)
            device_name TEXT,                               -- 測定対象の名前
            measurement_type TEXT DEFAULT 'General',        -- 測定種別（例: "IV Curve", "Frequency Response"）
            data JSONB NOT NULL,                            -- 測定データを格納するJSONBカラム（必須）
            operator_name TEXT DEFAULT 'Unknown',           -- 測定者の名前や識別子
            status TEXT DEFAULT 'raw',                      -- 測定データの状態
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP  -- 測定データの登録日時
        )
        """))

        conn.commit()  # 明示的にコミット

def migrate_db():
    engine = get_db_connection()
    with engine.connect() as conn:
        # gdsカラムを追加するALTER TABLE文
        conn.execute(text("""
            ALTER TABLE basic_performance
            ADD COLUMN gds DOUBLE PRECISION;
        """))

        conn.commit()  # 明示的にコミット

# データを取得する関数 (全データ取得)
def get_all_data():
    engine = get_db_connection()
    query = "SELECT * FROM data"
    query = text(query)  # クエリを text() でラップ
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    return df


def search_data(device_name=None, device_type=None, spice_string=None):
    engine = get_db_connection()
    
    # 動的なクエリを構築するためのリスト
    query = "SELECT * FROM data WHERE true"  # WHERE trueは常に真になるため、追加条件がある場合に便利
    params = {}
    
    if device_name:
        # リストが渡された場合、IN句を使用して検索
        if isinstance(device_name, list):
            query += " AND device_name ILIKE ANY(:device_name)"
            params["device_name"] = [f"%{name}%" for name in device_name]
        else:
            query += " AND device_name ILIKE :device_name"
            params["device_name"] = f"%{device_name}%"
    
    if device_type:
        # 同様に、device_typeもリストを使ってIN句を使用
        if isinstance(device_type, list):
            query += " AND device_type ILIKE ANY(:device_type)"
            params["device_type"] = [f"%{dtype}%" for dtype in device_type]
        else:
            query += " AND device_type ILIKE :device_type"
            params["device_type"] = f"%{device_type}%"
    
    if spice_string:
        if isinstance(spice_string, list):
            query += " AND spice_string ILIKE ANY(:spice_string)"
            params["spice_string"] = [f"%{s}%" for s in spice_string]
        else:
            query += " AND spice_string ILIKE :spice_string"
            params["spice_string"] = f"%{spice_string}%"
    
    # 構築されたクエリを実行
    query = text(query)  # クエリを text() でラップ
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params=params)
    return df


def get_data_by_id(data_id):
    engine = get_db_connection()
    query = "SELECT * FROM data WHERE id = :data_id"
    query = text(query)  # クエリを text() でラップ
    
    # パラメータを辞書として渡す
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"data_id": data_id})
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
def update_basic_performance(data_id, idss=None, gm=None, cgs=None, cgd=None, gds=None):
    engine = get_db_connection()
    with engine.connect() as conn:
        # data_idに対応するデータが存在するか確認
        result = conn.execute(text("SELECT * FROM basic_performance WHERE data_id = :data_id"), {"data_id": data_id}).fetchone()
        
        if result is None:
            # データが存在しない場合は新しく挿入
            conn.execute(text("""
                INSERT INTO basic_performance (data_id, idss, gm, cgs, cgd, gds)
                VALUES (:data_id, :idss, :gm, :cgs, :cgd, :gds)
            """), {"data_id": data_id, "idss": idss, "gm": gm, "cgs": cgs, "cgd": cgd, "gds": gds})
        else:
            # データが存在する場合は更新
            conn.execute(text("""
                UPDATE basic_performance
                SET idss = COALESCE(:idss, idss),
                    gm = COALESCE(:gm, gm),
                    cgs = COALESCE(:cgs, cgs),
                    cgd = COALESCE(:cgd, cgd),
                    gds = COALESCE(:gds, gds)
                WHERE data_id = :data_id
            """), {"idss": idss, "gm": gm, "cgs": cgs, "cgd": cgd, "gds": gds, "data_id": data_id})
        
        conn.commit()  # 明示的にコミット
    return True  # 更新または追加成功

def get_basic_performance_by_data_id(data_id):
    engine = get_db_connection()
    query = """
        SELECT * FROM basic_performance 
        WHERE data_id = :data_id
    """
    query = text(query)  # クエリを text() でラップ
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"data_id": data_id})
    return df

def get_all_device_ids():
    query = "SELECT id FROM data"  # 'id' を取得
    engine = get_db_connection()  # データベース接続のエンジンを取得
    with engine.connect() as conn:  # with構文で接続を管理
        result = conn.execute(text(query))
        device_ids = [row[0] for row in result.fetchall()]  # idをリストとして取得
    return device_ids


def add_experiment_data(data_id=None, device_name=None, measurement_type="General", data=None, operator_name="Unknown", status="raw"):
    """
    測定データをexperiment_dataテーブルに追加する関数。

    Parameters:
        data_id (int, optional): dataテーブルのID（指定しない場合はNULL）
        device_name (str, optional): デバイス名（data_idが指定されていない場合は必須）
        measurement_type (str): 測定種別（デフォルトは "General"）
        data (dict): 測定データ（JSON形式）
        operator_name (str): 測定者の名前（デフォルトは "Unknown"）
        status (str): 測定データの状態（デフォルトは "raw"）

    Returns:
        int: 新しく追加されたデータのID。エラーが発生した場合はNoneを返す。
    """
    if data_id is None and device_name is None:
        # data_id と device_name のどちらも指定されていない場合、エラー
        return None

    engine = get_db_connection()

    with engine.connect() as conn:
        # data_id が指定されている場合、その存在をチェック
        if data_id is not None:
            result = conn.execute(text("""
                SELECT id, device_name FROM data WHERE id = :data_id
            """), {"data_id": data_id}).fetchone()

            if result is None:
                # 指定された data_id が存在しない場合はエラー
                return None

            # data_id が指定されている場合、device_name を data テーブルから取得したものに上書き
            device_name = result[1]

        # data_id が指定されていない場合、device_name から data_id を取得
        if data_id is None and device_name is not None:
            result = conn.execute(text("""
                SELECT id FROM data WHERE device_name = :device_name
            """), {"device_name": device_name}).fetchone()

            if result:
                data_id = result[0]

        # 新しい測定データをexperiment_dataテーブルに追加
        try:
            result = conn.execute(text("""
                INSERT INTO experiment_data (data_id, device_name, measurement_type, data, operator_name, status)
                VALUES (:data_id, :device_name, :measurement_type, :data, :operator_name, :status)
                RETURNING id
            """), {
                "data_id": data_id,  # data_id が None の場合は NULL として挿入される
                "device_name": device_name,
                "measurement_type": measurement_type,
                "data": data,
                "operator_name": operator_name,
                "status": status
            })
            
            # 追加した測定データのIDを取得
            new_id = result.fetchone()[0]
            # コミットして変更を確定
            conn.commit()
            return new_id  # 追加した測定データのIDを返す
        except IntegrityError:
            # 重複などのエラーが発生した場合はロールバック
            conn.rollback()
            return None


def get_experiment_data_by_id_or_data_id(identifier, by_data_id=False):
    """
    experiment_dataテーブルから指定されたidentifier（experiment_idまたはdata_id）に関連する実験データを取得し、Pandas DataFrameに変換する関数。

    Parameters:
        identifier (int): experiment_idまたはdata_idに基づく実験データの取得
        by_data_id (bool): Trueの場合はdata_idを基に検索、Falseの場合はexperiment_idを基に検索

    Returns:
        pd.DataFrame: 実験データをPandas DataFrameに変換したもの
    """
    engine = get_db_connection()

    if by_data_id:
        query = """
            SELECT id, device_name, measurement_type, data, operator_name, status, created_at
            FROM experiment_data
            WHERE data_id = :identifier
        """
    else:
        query = """
            SELECT id, device_name, measurement_type, data, operator_name, status, created_at
            FROM experiment_data
            WHERE id = :identifier
        """
    
    query = text(query)  # クエリを text() でラップ

    # クエリ結果をPandas DataFrameに変換
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"identifier": identifier})

    return df

def get_experiment_data(include_all=False, exclude_data=False):
    """
    experiment_dataテーブルからデータを取得し、Pandas DataFrameに変換する関数。
    include_allがTrueの場合、すべてのデータを返します。
    exclude_dataがTrueの場合、dataフィールドを除外します。

    Args:
        include_all (bool): Trueの場合、すべてのデータを取得。
                            Falseの場合、data_idがNULLのデータのみを取得。
        exclude_data (bool): Trueの場合、dataフィールドを除外。

    Returns:
        pd.DataFrame: 実験データをPandas DataFrameに変換したもの。
    """
    engine = get_db_connection()
    
    # 取得するフィールドを動的に設定
    fields = [
        "id", 
        "device_name", 
        "measurement_type", 
        "operator_name", 
        "status", 
        "created_at"
    ]
    if not exclude_data:
        fields.insert(3, "data")  # dataフィールドを含む場合に追加

    # クエリを作成
    query = f"""
        SELECT {', '.join(fields)}
        FROM experiment_data
    """
    if not include_all:
        query += " WHERE data_id IS NULL"
    
    query = text(query)  # クエリを text() でラップ
    
    # クエリ結果をPandas DataFrameに変換
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)

    return df

def update_data_id_for_experiment_data(experiment_data_id, new_data_id):
    """
    指定されたexperiment_dataのidに基づいて、data_idを更新する関数。

    Parameters:
        experiment_data_id (int): 更新するexperiment_dataの固有のID
        new_data_id (int or None): 新しいdata_id。Noneの場合はdata_idをNULLに設定

    Returns:
        bool: 更新が成功した場合はTrue、失敗した場合はFalse
    """
    engine = get_db_connection()

    with engine.connect() as conn:
        try:
            # experiment_dataのidを指定してdata_idを更新
            result = conn.execute(text("""
                UPDATE experiment_data
                SET data_id = :new_data_id
                WHERE id = :experiment_data_id
            """), {
                "experiment_data_id": experiment_data_id,
                "new_data_id": new_data_id
            })

            # 更新された行数をチェック
            if result.rowcount > 0:
                conn.commit()  # 更新が成功した場合、コミット
                return True
            else:
                return False  # 該当するIDが存在しない場合は更新なし
        except Exception as e:
            # エラーが発生した場合はロールバック
            conn.rollback()
            print(f"Error: {e}")
            return False