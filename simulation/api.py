import os
from flask import Flask, request, send_file
from PyLTSpice import SimRunner, LTspice, SpiceEditor
import zipfile
from io import BytesIO

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SIMULATION_DIR = os.path.join(BASE_DIR, "data")

os.makedirs(SIMULATION_DIR, exist_ok=True)

def run_simulation(net_file_path):
    """シミュレーションを実行してRAWデータとログを取得"""
    runner = SimRunner(output_folder=SIMULATION_DIR, simulator=LTspice)
    net = SpiceEditor(net_file_path)
    raw_path, log_path = runner.run_now(net, run_filename=net_file_path)
    return raw_path, log_path

@app.route("/")
def home():
    return "API is running!"  # トップページに表示するメッセージ

@app.route("/simulate", methods=["POST"])
def simulate():
    if "file" not in request.files:
        return "No file part", 400

    file = request.files["file"]
    if file.filename == "":
        return "No selected file", 400

    # アップロードされたファイルの保存パス
    net_file_path = os.path.join(SIMULATION_DIR, file.filename)

    try:
        file.save(net_file_path)
    except Exception as e:
        return f"Failed to save file: {e}", 500

    try:
        raw_file_path, log_file_path = run_simulation(net_file_path)
    except Exception as e:
        return f"Simulation failed: {e}", 500

    try:
        raw_file_name = os.path.basename(raw_file_path)
        log_file_name = os.path.basename(log_file_path)

        # メモリ上でZIPアーカイブを作成
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # RAWファイルを圧縮
            with open(raw_file_path, 'rb') as raw_file:
                zip_file.writestr(raw_file_name, raw_file.read())
            # LOGファイルを圧縮
            with open(log_file_path, 'rb') as log_file:
                zip_file.writestr(log_file_name, log_file.read())

        zip_buffer.seek(0)

        # レスポンスを返す前にファイルを削除
        os.remove(net_file_path)
        os.remove(raw_file_path)
        os.remove(log_file_path)

        return send_file(zip_buffer, as_attachment=True, attachment_filename="simulation_results.zip")

    except Exception as e:
        return f"Failed to send .raw or .log file: {e}", 500

if __name__ == "__main__":
    app.run(debug=False, port=5900)
