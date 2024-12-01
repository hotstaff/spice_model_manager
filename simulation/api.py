import os
from datetime import datetime
from io import BytesIO
import zipfile
from flask import Flask, request, send_file, render_template
from PyLTSpice import SimRunner, LTspice, SpiceEditor

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SIMULATION_DIR = os.path.join(BASE_DIR, "data")

os.makedirs(SIMULATION_DIR, exist_ok=True)

# 月と日付、時刻の略記を使ってファイル名を生成
def generate_short_zip_filename(base_name):
    timestamp = datetime.now().strftime("%b_%d_%H%M")  # 例: Dec_01_1345
    return f"{base_name}_{timestamp}.zip"

def run_simulation(uploaded_file_path):
    """シミュレーションを実行してRAWデータとログを取得"""
    runner = SimRunner(output_folder=SIMULATION_DIR, simulator=LTspice)

    # .ascファイルを元に、.netファイルを生成
    if uploaded_file_path.endswith('.asc'):
        netlist_path = runner.create_netlist(uploaded_file_path)  # .net ファイルの作成
    else:
        netlist_path = uploaded_file_path  # .netファイルがすでにある場合はそのまま使う

    # シミュレーションを実行
    net = SpiceEditor(netlist_path)  # 作成したまたはアップロードされた.netファイルを使う
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

@app.route("/")
def home():
    return render_template("index.html")  # テンプレートを表示

@app.route("/simulate", methods=["POST"])
def simulate():
    if "file" not in request.files:
        return "No file part", 400

    file = request.files["file"]
    if file.filename == "":
        return "No selected file", 400

    # アップロードされたファイルの保存パス
    uploaded_file_path = os.path.join(SIMULATION_DIR, file.filename)

    try:
        file.save(uploaded_file_path)
        raw_file_path, log_file_path, netlist_path = run_simulation(uploaded_file_path)
        
        # メモリ上でZIPアーカイブを作成
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # RAWファイルを圧縮
            zip_file.write(raw_file_path, os.path.basename(raw_file_path))
            # LOGファイルを圧縮
            zip_file.write(log_file_path, os.path.basename(log_file_path))

            # アップロードされたファイルと関連ファイルを圧縮
            zip_file.write(uploaded_file_path, os.path.basename(uploaded_file_path))

            if uploaded_file_path.endswith('.asc'):
                zip_file.write(netlist_path, os.path.basename(netlist_path))

        zip_buffer.seek(0)

        # ファイル削除
        cleanup_files([uploaded_file_path, raw_file_path, log_file_path])

        zip_filename = generate_short_zip_filename(os.path.splitext(os.path.basename(netlist_path))[0])

        return send_file(zip_buffer, as_attachment=True, download_name=zip_filename)

    except Exception as e:
        # エラーハンドリング
        cleanup_files([uploaded_file_path, raw_file_path, log_file_path])
        return f"Error during simulation or file handling: {e}", 500

if __name__ == "__main__":
    app.run(debug=False, port=5000)
