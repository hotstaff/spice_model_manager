import os
import random
import string
import pickle
from datetime import datetime
from flask import Flask, request, send_file, jsonify, render_template
from redis import Redis

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SIMULATION_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(SIMULATION_DIR, exist_ok=True)

redis = Redis(host="localhost", port=6379, db=0)
REDIS_JOB_PREFIX = "job:"
MAX_JOBS = 100

def generate_job_id_from_timestamp(base_name):
    timestamp = datetime.now().strftime("%b_%d_%H%M")
    random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=7))
    return f"{base_name}_{timestamp}_{random_suffix}"

def create_job(uploaded_file_path):
    base_name = os.path.splitext(os.path.basename(uploaded_file_path))[0]
    job_id = generate_job_id_from_timestamp(base_name)
    job_data = {
        "status": "pending",
        "result": None,
        "error": None,
        "file_path": uploaded_file_path,
    }
    redis.set(f"{REDIS_JOB_PREFIX}{job_id}", pickle.dumps(job_data))

    all_jobs = redis.keys(f"{REDIS_JOB_PREFIX}*")
    if len(all_jobs) > MAX_JOBS:
        oldest_job_key = sorted(all_jobs)[0]
        redis.delete(oldest_job_key)

    return job_id

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
    return f"Simulation job created with ID: {job_id}. Worker will process it.", 202

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
    job_key = f"{REDIS_JOB_PREFIX}{job_id}"
    job_data = redis.get(job_key)
    if not job_data:
        return jsonify({"error": "Job not found"}), 404

    job_data = pickle.loads(job_data)
    return jsonify({"job_id": job_id, "status": job_data["status"]})

@app.route("/api/simulations/<job_id>/result", methods=["GET"])
def api_simulation_result(job_id):
    job_key = f"{REDIS_JOB_PREFIX}{job_id}"
    job_data = redis.get(job_key)
    if not job_data:
        return jsonify({"error": "Job not found"}), 404

    job_data = pickle.loads(job_data)
    if job_data["status"] != "completed":
        return jsonify({"error": "Job not completed"}), 400

    zip_buffer = job_data["result"]
    zip_buffer.seek(0)
    return send_file(zip_buffer, as_attachment=True, download_name=f"{job_id}.zip")

if __name__ == "__main__":
    app.run(debug=False, port=5000)
