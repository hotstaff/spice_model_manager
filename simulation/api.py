import os
import random
import string
from datetime import datetime
from io import BytesIO
import zipfile
from flask import Flask, request, send_file, render_template, jsonify
from PyLTSpice import SimRunner, LTspice, SpiceEditor

import threading
import pickle
from redis import Redis

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SIMULATION_DIR = os.path.join(BASE_DIR, "data")

os.makedirs(SIMULATION_DIR, exist_ok=True)

# Redis設定
redis = Redis(host="localhost", port=6379, db=0)
REDIS_JOB_PREFIX = "job:"  # Redisキーのプレフィックス
MAX_JOBS = 100  # 最大ジョブ数

# 基本のファイル名から日付を使ってジョブIDを生成
def generate_job_id_from_timestamp(base_name):
    """月と日付、時刻の略記を使ってユニークなジョブIDを生成"""
    timestamp = datetime.now().strftime("%b_%d_%H%M")  # 例: Dec_01_1345
    random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=7))
    return f"{base_name}_{timestamp}_{random_suffix}"

# Redisを使ったジョブ操作
def create_job(uploaded_file_path):
    """ジョブをRedisに作成し登録"""
    base_name = os.path.splitext(os.path.basename(uploaded_file_path))[0]
    job_id = generate_job_id_from_timestamp(base_name)
    job_data = {
        "status": "pending",
        "result": None,
        "error": None,
        "file_path": uploaded_file_path,
    }
    redis.set(f"{REDIS_JOB_PREFIX}{job_id}", pickle.dumps(job_data))

    # ジョブ数を制限
    all_jobs = redis.keys(f"{REDIS_JOB_PREFIX}*")
    if len(all_jobs) > MAX_JOBS:
        oldest_job_key = sorted(all_jobs)[0]  # 最古のジョブを削除
        redis.delete(oldest_job_key)

    return job_id

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

def get_all_jobs():
    """すべてのジョブを取得"""
    all_jobs = {}
    for job_key in redis.keys(f"{REDIS_JOB_PREFIX}*"):
        job_id = job_key.decode("utf-8").replace(REDIS_JOB_PREFIX, "")
        job_data = pickle.loads(redis.get(job_key))
        all_jobs[job_id] = job_data
    return all_jobs

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

def run_job(job_id, async_mode=False):
    """ジョブを実行"""
    def job_runner():
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

    if async_mode:
        threading.Thread(target=job_runner).start()
    else:
        job_runner()

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/simulate", methods=["POST"])
def simulate():
    file = request.files.get("file")
    if not file or file.filename == "":
        return "No file uploaded or filename is empty", 400

    uploaded_file_path = os.path.join(SIMULATION_DIR, file.filename)
    file.save(uploaded_file_path)

    job_id = create_job(uploaded_file_path)
    run_job(job_id)

    job = get_job(job_id)
    if job["status"] == "completed":
        zip_buffer = job["result"]
        zip_buffer.seek(0)
        zip_filename = f"{job_id}.zip"
        return send_file(zip_buffer, as_attachment=True, download_name=zip_filename)
    else:
        return f"Error during simulation: {job.get('error', 'Unknown error')}", 500

@app.route("/api/simulate", methods=["POST"])
def api_simulate():
    file = request.files.get("file")
    if not file or file.filename == "":
        return jsonify({"error": "No file uploaded or filename is empty"}), 400

    uploaded_file_path = os.path.join(SIMULATION_DIR, file.filename)
    file.save(uploaded_file_path)

    job_id = create_job(uploaded_file_path)
    run_job(job_id, async_mode=True)

    return jsonify({"job_id": job_id}), 202

@app.route("/api/simulations/<job_id>", methods=["GET"])
def api_simulation_status(job_id):
    job = get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify({"job_id": job_id, "status": job["status"]})

@app.route("/api/simulations/<job_id>/result", methods=["GET"])
def api_simulation_result(job_id):
    job = get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    if job["status"] != "completed":
        return jsonify({"error": "Job not completed"}), 400

    zip_buffer = job["result"]
    zip_buffer.seek(0)
    return send_file(zip_buffer, as_attachment=True, download_name=f"{job_id}.zip")

@app.route("/api/simulations", methods=["GET"])
def api_simulations():
    jobs = get_all_jobs()
    return jsonify({job_id: {"status": job["status"], "error": job.get("error")} for job_id, job in jobs.items()})

if __name__ == "__main__":
    app.run(debug=False, port=5000)
