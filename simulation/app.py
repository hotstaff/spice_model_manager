import os
import random
import string
import json
from io import BytesIO
from datetime import datetime
from flask import Flask, request, send_file, jsonify, render_template
from redis import Redis

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SIMULATION_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(SIMULATION_DIR, exist_ok=True)

redis = Redis(host="localhost", port=6379, db=0, decode_responses=False)
REDIS_JOB_PREFIX = "job:"
REDIS_RESULT_PREFIX = "result:"
MAX_JOBS = 100

def get_job_meta(job_id):
    """ジョブのメタデータを取得"""
    job_key = f"{REDIS_JOB_PREFIX}{job_id}:meta"
    job_data = redis.get(job_key)
    if job_data:
        return json.loads(job_data.decode('utf-8'))  # 文字列としてデコードしてからJSONパース
    return None

def get_job_file(job_id):
    """ジョブのファイルデータを取得"""
    file_key = f"{REDIS_JOB_PREFIX}{job_id}:file"
    return redis.get(file_key)

def generate_job_id_from_timestamp(base_name):
    timestamp = datetime.now().strftime("%b_%d_%H%M")
    random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=7))
    return f"{base_name}_{timestamp}_{random_suffix}"

def create_job(uploaded_file_path):
    base_name = os.path.splitext(os.path.basename(uploaded_file_path))[0]
    job_id = generate_job_id_from_timestamp(base_name)
    
    # アップロードされたファイルを読み込む
    with open(uploaded_file_path, "rb") as file:
        binary_data = file.read()

    # ジョブのメタデータ
    job_data = {
        "status": "pending",
        "error": None,
        "file_path": uploaded_file_path,
    }

    # メタデータを保存
    redis.set(f"{REDIS_JOB_PREFIX}{job_id}:meta", json.dumps(job_data))

    # アップロードファイルのバイナリデータを保存
    redis.set(f"{REDIS_JOB_PREFIX}{job_id}:file", binary_data)

    # ジョブの過剰保存を防ぐ
    all_jobs = redis.keys(f"{REDIS_JOB_PREFIX}*:meta")
    if len(all_jobs) > MAX_JOBS:
        oldest_job_key = sorted(all_jobs)[0]
        redis.delete(oldest_job_key.replace(":meta", ":file"))
        redis.delete(oldest_job_key)

    return job_id

def get_all_jobs():
    """すべてのジョブをRedisから取得して辞書形式で返す"""
    all_jobs = {}
    for job_key in redis.keys(f"{REDIS_JOB_PREFIX}*:meta"):
        job_id = job_key.replace(REDIS_JOB_PREFIX, "").replace(":meta", "")
        job_data = json.loads(redis.get(job_key).decode('utf-8'))
        all_jobs[job_id] = job_data
    return all_jobs

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

    # ジョブを登録
    job_id = create_job(uploaded_file_path)
    return jsonify({"job_id": job_id}), 202

@app.route("/api/simulations", methods=["GET"])
def api_simulations():
    # Redisから全ジョブを取得
    jobs = get_all_jobs()
    return jsonify({
        job_id: {
            "status": job["status"],
            "error": job.get("error", None)
        }
        for job_id, job in jobs.items()
    })

@app.route("/api/simulate", methods=["POST"])
def api_simulate():
    file = request.files.get("file")
    if not file or file.filename == "":
        return jsonify({"error": "No file uploaded or filename is empty"}), 400

    uploaded_file_path = os.path.join(SIMULATION_DIR, file.filename)
    file.save(uploaded_file_path)

    job_id = create_job(uploaded_file_path)
    return jsonify({"job_id": job_id}), 202

@app.route("/api/simulations/<job_id>", methods=["GET"])
def api_simulation_status(job_id):
    job_data = get_job_meta(job_id)
    return jsonify({"job_id": job_id, "status": job_data["status"]})

@app.route("/api/simulations/<job_id>/result", methods=["GET"])
def api_simulation_result(job_id):
    result_key = f"{REDIS_RESULT_PREFIX}{job_id}"
    job_data = get_job_meta(job_id)

    if not job_data:
        return jsonify({"error": "Job not found"}), 404

    if job_data["status"] != "completed":
        return jsonify({"error": "Job not completed"}), 400

    binary_data = redis.get(result_key)
    if not binary_data:
        return jsonify({"error": "Result data not found"}), 404


    return

    # バイナリデータを返却
    return send_file(
        BytesIO(binary_data),  # BytesIOでラップ
        as_attachment=True,
        download_name=f"{job_id}.zip"
    )

if __name__ == "__main__":
    app.run(debug=False, port=5000)
