import psycopg2
import pandas as pd

# データベース接続のための関数
def get_db_connection():
    conn = psycopg2.connect(
        dbname="spice-model-storage",
        user="your_username",
        password="your_password",
        host="your_host_address",
        port="5432"
    )
    return conn

# テーブルの初期化
def init_db():
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
    conn.commit()
    conn.close()

# データを取得する関数 (全データ取得)
def get_all_data():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM data", conn)
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
