import os
import threading
import json
from redis import Redis
from datetime import datetime
from io import BytesIO
import zipfile
from PyLTSpice import SimRunner, LTspice, SpiceEditor

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SIMULATION_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(SIMULATION_DIR, exist_ok=True)

# 環境変数からRedisの接続情報を取得
REDIS_HOST = os.environ.get("REDISHOST", "localhost")  # デフォルトはlocalhost
REDIS_PORT = int(os.environ.get("REDISPORT", 6379))    # デフォルトは6379
REDIS_DB = int(os.environ.get("REDISDB", 0))           # デフォルトはDB 0

redis = Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
REDIS_JOB_PREFIX = "job:"
REDIS_RESULT_PREFIX = "result:"

def run_simulation(uploaded_file_path):
    """シミュレーションを実行してRAWデータとログを取得"""
    runner = SimRunner(output_folder=SIMULATION_DIR, simulator=LTspice)
    if uploaded_file_path.endswith('.asc'):
        netlist_path = runner.create_netlist(uploaded_file_path)
    else:
        netlist_path = uploaded_file_path
    net = SpiceEditor(netlist_path)
    raw_path, log_path = runner.run_now(net, run_filename=netlist_path)
    return raw_path, log_path, netlist_path

def cleanup_files(files):
    """一時ファイル削除"""
    for file in files:
        try:
            if os.path.exists(file):
                os.remove(file)
        except Exception as e:
            print(f"Failed to delete file {file}: {e}")

def update_job(job_id, **kwargs):
    """ジョブ情報を更新"""
    job_key = f"{REDIS_JOB_PREFIX}{job_id}:meta"
    job_data = json.loads(redis.get(job_key))
    job_data.update(kwargs)
    redis.set(job_key, json.dumps(job_data))

def get_job_meta(job_id):
    """ジョブのメタデータを取得"""
    job_key = f"{REDIS_JOB_PREFIX}{job_id}:meta"
    job_data = redis.get(job_key)
    return json.loads(job_data) if job_data else None

def get_job_file(job_id):
    """ジョブのファイルデータを取得"""
    file_key = f"{REDIS_JOB_PREFIX}{job_id}:file"
    return redis.get(file_key)

def run_job(job_id):
    """ジョブを実行"""
    try:
        # メタデータを取得
        job_data = get_job_meta(job_id)
        if not job_data:
            print(f"Job {job_id} metadata not found.")
            return

        # ファイルデータを取得して一時ファイルに保存
        binary_file = get_job_file(job_id)
        if not binary_file:
            print(f"Job {job_id} file data not found.")
            update_job(job_id, status="failed", error="File data missing.")
            return

        uploaded_file_path = os.path.join(SIMULATION_DIR, f"{job_id}_uploaded")
        with open(uploaded_file_path, "wb") as f:
            f.write(binary_file)

        # シミュレーションを実行
        raw_file_path, log_file_path, netlist_path = run_simulation(uploaded_file_path)

        # 結果をZIPにまとめる
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.write(raw_file_path, os.path.basename(raw_file_path))
            zip_file.write(log_file_path, os.path.basename(log_file_path))
            zip_file.write(uploaded_file_path, os.path.basename(uploaded_file_path))
            if uploaded_file_path.endswith('.asc'):
                zip_file.write(netlist_path, os.path.basename(netlist_path))
        zip_buffer.seek(0)

        # 結果データを保存
        result_key = f"{REDIS_RESULT_PREFIX}{job_id}"
        redis.set(result_key, zip_buffer.getvalue())

        # ジョブステータス更新
        update_job(job_id, status="completed", result_key=result_key)

        # 一時ファイルを削除
        cleanup_files([uploaded_file_path, raw_file_path, log_file_path])
    except Exception as e:
        print(f"Error processing job {job_id}: {e}")
        update_job(job_id, status="failed", error=str(e))

def job_worker():
    """ジョブを定期的に確認して実行"""
    while True:
        for job_key in redis.keys(f"{REDIS_JOB_PREFIX}*:meta"):
            job_id = job_key.decode("utf-8").replace(f"{REDIS_JOB_PREFIX}", "").replace(":meta", "")
            job_data = get_job_meta(job_id)

            # ジョブが存在しない場合や処理中の場合スキップ
            if not job_data or job_data["status"] != "pending":
                continue

            run_job(job_id)

if __name__ == "__main__":
    job_worker()
