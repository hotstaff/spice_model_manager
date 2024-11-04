import sqlite3
import pandas as pd

# データベース接続のための関数
def get_db_connection():
    conn = sqlite3.connect('data.db')
    conn.row_factory = sqlite3.Row  # 辞書形式で行を取得
    return conn

# テーブルの初期化
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        column1 TEXT,
        column2 TEXT
    )
    """)
    conn.commit()
    conn.close()

# データを取得する関数
def get_all_data():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM data", conn)
    conn.close()
    return df

# 特定のIDのデータを取得する関数
def get_data_by_id(data_id):
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM data WHERE id = ?", conn, params=(data_id,))
    conn.close()
    return df

# データを新規追加する関数
def add_data(column1, column2):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO data (column1, column2) VALUES (?, ?)", (column1, column2))
    conn.commit()
    conn.close()

# データを更新する関数
def update_data(data_id, column1=None, column2=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM data WHERE id = ?", (data_id,))
    if cursor.fetchone() is None:
        conn.close()
        return False  # データが存在しない場合
    
    cursor.execute("""
        UPDATE data
        SET column1 = COALESCE(?, column1),
            column2 = COALESCE(?, column2)
        WHERE id = ?
    """, (column1, column2, data_id))
    conn.commit()
    conn.close()
    return True  # 更新成功

# データを削除する関数
def delete_data(data_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM data WHERE id = ?", (data_id,))
    if cursor.fetchone() is None:
        conn.close()
        return False  # データが存在しない場合
    
    cursor.execute("DELETE FROM data WHERE id = ?", (data_id,))
    conn.commit()
    conn.close()
    return True  # 削除成功
