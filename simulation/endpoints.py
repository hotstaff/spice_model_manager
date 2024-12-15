#インポート用
import sys
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

import os
from flask import Flask, Blueprint, request, send_file, jsonify, render_template
from job_model import JobModel
from io import BytesIO

simulation = Blueprint('simulation', __name__)

redis_host = os.getenv("REDIS_HOST", "localhost")  # デフォルトはlocalhost

# JobModelのインスタンスを作成
job_model = JobModel(redis_host=redis_host, redis_port=6379, redis_db=0)

@simulation.route("/api/clear_jobs", methods=["POST"])
def clear_redis_jobs():
    """Redisのジョブをすべて削除"""
    result = job_model.clear_all_jobs()  # JobModelのメソッドを呼び出し
    return jsonify({"message": result})


@simulation.route("/")
def home():
    return render_template("index.html")


@simulation.route("/simulate", methods=["POST"])
def simulate():
    file = request.files.get("file")
    if not file or file.filename == "":
        return "No file uploaded or filename is empty", 400

    uploaded_file_path = os.path.join(job_model.SIMULATION_DIR, file.filename)
    file.save(uploaded_file_path)

    # ジョブを登録
    job_id = job_model.create_job(uploaded_file_path)
    return jsonify({"job_id": job_id}), 202


@simulation.route("/api/simulations", methods=["GET"])
def api_simulations():
    jobs = job_model.get_all_jobs()
    return jsonify({
        job_id: {
            "status": job["status"],
            "error": job.get("error", None)
        }
        for job_id, job in jobs.items()
    })


@simulation.route("/api/simulate", methods=["POST"])
def api_simulate():
    file = request.files.get("file")
    if not file or file.filename == "":
        return jsonify({"error": "No file uploaded or filename is empty"}), 400

    uploaded_file_path = os.path.join(job_model.SIMULATION_DIR, file.filename)
    file.save(uploaded_file_path)

    job_id = job_model.create_job(uploaded_file_path)
    return jsonify({"job_id": job_id}), 202


@simulation.route("/api/simulations/<job_id>", methods=["GET"])
def api_simulation_status(job_id):
    job_data = job_model.get_job_meta(job_id)
    if job_data is None:
        return jsonify({"error": f"Job with ID {job_id} not found."}), 404
    return jsonify({"job_id": job_id, "status": job_data.get("status", "unknown")})


@simulation.route("/api/simulations/<job_id>/result", methods=["GET"])
def api_simulation_result(job_id):
    job_data = job_model.get_job_meta(job_id)

    if not job_data:
        return jsonify({"error": "Job not found"}), 404

    if job_data["status"] != "completed":
        return jsonify({"error": "Job not completed"}), 400

    binary_data = job_model.get_job_result(job_id)
    if not binary_data:
        return jsonify({"error": "Result data not found"}), 404

    return send_file(
        BytesIO(binary_data),
        as_attachment=True,
        download_name=f"{job_id}.zip"
    )
