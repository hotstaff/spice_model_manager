import os
import uuid
from datetime import datetime
from io import BytesIO
import zipfile
from flask import Flask, request, send_file, render_template, jsonify
from PyLTSpice import SimRunner, LTspice, SpiceEditor

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SIMULATION_DIR = os.path.join(BASE_DIR, "data")

os.makedirs(SIMULATION_DIR, exist_ok=True)

# ジョブ管理用辞書
jobs = {}

def generate_short_zip_filename(base_name):
    """月と日付、時刻の略記を使ってファイル名を生成"""
    timestamp = datetime.now().strftime("%b_%d_%H%M")  # 例: Dec_01_1345
    return f"{base_name}_{timestamp}.zip"

def run_simulation(uploaded_file_path):
    """シミュレーションを実行してRAWデータとログを取得"""
    runner = SimRunner(output_folder=SIMULATION_DIR, simulator=LTspice)

    # .ascファイルを元に、.netファイルを生成
    if uploaded_file_path.endswith('.asc'):
        netlist_path = runner.create_netlist(uploaded_file_path)
    else:
        netlist_path = uploaded_file_path

    # シミュレーションを実行
    net = SpiceEditor(netlist_path)
    raw_path, log_path = runner.run_now(net, run_filename=netlist_path)
    return raw_path, log_path, netlist_path

def cleanup_files(files):
    """一時的に保存されたファイルを削除"""
    for file in files:
        try:
            if os.path.exists(file):
                os.remove(file)
        except Exception as e:
            print(f"Failed to delete file {file}: {e}")


def create_job(uploaded_file_path):
    """ジョブを作成し登録"""
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "pending", "result": None, "error": None, "file_path": uploaded_file_path}
    return job_id


def run_job(job_id, async_mode=False):
    """ジョブを実行"""
    def job_runner():
        try:
            uploaded_file_path = jobs[job_id]["file_path"]
            raw_file_path, log_file_path, netlist_path = run_simulation(uploaded_file_path)

            # 結果をZIPファイルとしてまとめる
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                zip_file.write(raw_file_path, os.path.basename(raw_file_path))
                zip_file.write(log_file_path, os.path.basename(log_file_path))
                zip_file.write(uploaded_file_path, os.path.basename(uploaded_file_path))

                if uploaded_file_path.endswith('.asc'):
                    zip_file.write(netlist_path, os.path.basename(netlist_path))

            zip_buffer.seek(0)
            jobs[job_id]["status"] = "completed"
            jobs[job_id]["result"] = zip_buffer

            # 一時ファイルをクリーンアップ
            cleanup_files([uploaded_file_path, raw_file_path, log_file_path])

        except Exception as e:
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["error"] = str(e)

    if async_mode:
        # 非同期処理用 (例: 本番環境でスレッドやCeleryを利用)
        from threading import Thread
        Thread(target=job_runner).start()
    else:
        # 同期処理（すぐに実行）
        job_runner()

@app.route("/")
def home():
    return render_template("index.html")  # 現在のブラウザUI用

@app.route("/simulate", methods=["POST"])
def simulate():
    """ブラウザ経由のシミュレーション実行"""
    file = request.files.get("file")
    if not file or file.filename == "":
        return "No file uploaded or filename is empty", 400

    uploaded_file_path = os.path.join(SIMULATION_DIR, file.filename)
    file.save(uploaded_file_path)

    # ブラウザ用はジョブ完了まで待つ
    job_id = create_job(uploaded_file_path)
    run_job(job_id)

    job = jobs[job_id]
    if job["status"] == "completed":
        zip_buffer = job["result"]
        zip_buffer.seek(0)
        zip_filename = generate_short_zip_filename(os.path.splitext(os.path.basename(uploaded_file_path))[0])
        return send_file(zip_buffer, as_attachment=True, download_name=zip_filename)
    else:
        return f"Error during simulation: {job.get('error', 'Unknown error')}", 500


@app.route("/api/simulate", methods=["POST"])
def api_simulate():
    """ジョブ形式のシミュレーション登録"""
    file = request.files.get("file")
    if not file or file.filename == "":
        return jsonify({"error": "No file uploaded or filename is empty"}), 400

    uploaded_file_path = os.path.join(SIMULATION_DIR, file.filename)
    file.save(uploaded_file_path)

    job_id = create_job(uploaded_file_path)

    # 非同期的に処理を開始
    run_job(job_id, async_mode=True)

    return jsonify({"job_id": job_id}), 202


@app.route("/api/simulations/<job_id>", methods=["GET"])
def api_simulation_status(job_id):
    """ジョブのステータス確認"""
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify({"job_id": job_id, "status": job["status"]})

@app.route("/api/simulations/<job_id>/result", methods=["GET"])
def api_simulation_result(job_id):
    """シミュレーション結果をダウンロード"""
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    if job["status"] != "completed":
        return jsonify({"error": "Job not completed"}), 400

    zip_buffer = job["result"]
    zip_buffer.seek(0)
    return send_file(zip_buffer, as_attachment=True, download_name=f"{job_id}.zip")

if __name__ == "__main__":
    app.run(debug=False, port=5000)
