import os
import threading
import pickle
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
    job_key = f"{REDIS_JOB_PREFIX}{job_id}"
    job_data = pickle.loads(redis.get(job_key))
    job_data.update(kwargs)
    redis.set(job_key, pickle.dumps(job_data))

def get_job(job_id):
    """ジョブ情報を取得"""
    job_key = f"{REDIS_JOB_PREFIX}{job_id}"
    job_data = redis.get(job_key)
    return pickle.loads(job_data) if job_data else None

def run_job(job_id):
    """ジョブを実行"""
    try:
        job_data = get_job(job_id)
        uploaded_file_path = job_data["file_path"]

        raw_file_path, log_file_path, netlist_path = run_simulation(uploaded_file_path)

        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.write(raw_file_path, os.path.basename(raw_file_path))
            zip_file.write(log_file_path, os.path.basename(log_file_path))
            zip_file.write(uploaded_file_path, os.path.basename(uploaded_file_path))
            if uploaded_file_path.endswith('.asc'):
                zip_file.write(netlist_path, os.path.basename(netlist_path))
        zip_buffer.seek(0)

        update_job(job_id, status="completed", result=zip_buffer)

        cleanup_files([uploaded_file_path, raw_file_path, log_file_path])
    except Exception as e:
        update_job(job_id, status="failed", error=str(e))

def job_worker():
    """ジョブを定期的に確認して実行"""
    while True:
        for job_key in redis.keys(f"{REDIS_JOB_PREFIX}*"):
            job_id = job_key.decode("utf-8").replace(REDIS_JOB_PREFIX, "")
            job_data = get_job(job_id)

            # get_jobがNoneを返した場合に処理をスキップ
            if job_data is None:
                print(f"Job {job_id} not found or not valid.")
                continue

            if job_data["status"] == "pending":
                run_job(job_id)

if __name__ == "__main__":
    job_worker()
