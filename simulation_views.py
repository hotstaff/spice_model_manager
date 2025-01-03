import os
from io import BytesIO
from flask import Flask, Blueprint, request, send_file, jsonify, render_template

# 自作モジュールのインポート
from models.db_model import get_all_device_ids

from simulation.job_model import JobModel
from simulation.file_extractor import FileExtractor
from simulation.jfet import JFET_IV_Characteristic, JFET_Vgs_Id_Characteristic, JFET_Gm_Vgs_Characteristic, JFET_Gm_Id_Characteristic
from client.spice_model_parser import SpiceModelParser
from forms import AddModelForm  # AddModelFormをインポート

from tasks import run_basic_performance_simulation, run_and_store_plots

# Blueprintの定義
simu_views = Blueprint('simu_views', __name__)

# Redisホストの設定
redis_host = os.getenv("REDIS_HOST", "localhost")  # デフォルトはlocalhost

# Zipファイル用
file_extractor = FileExtractor()

# JobModelのインスタンスを作成
job_model = JobModel(redis_host=redis_host)

@simu_views.errorhandler(413)
def request_entity_too_large(error):
    """ファイルサイズ超過エラーのハンドリング"""
    return jsonify({"error": "File size exceeds the 1MB limit"}), 413


@simu_views.route("/api/simulations", methods=["GET"])
def api_simulations():
    jobs = job_model.get_all_jobs()
    return jsonify({
        job_id: {
            "status": job["status"],
            "error": job.get("error", None)
        }
        for job_id, job in jobs.items()
    })


@simu_views.route("/api/simulations/<job_id>", methods=["GET"])
def api_simulation_status(job_id):
    job_data = job_model.get_job_meta(job_id)
    if job_data is None:
        return jsonify({"error": f"Job with ID {job_id} not found."}), 404
    return jsonify({"job_id": job_id, "status": job_data.get("status", "unknown")})


@simu_views.route("/api/simulations/<job_id>/result", methods=["GET"])
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

@simu_views.route("/api/simulate", methods=["POST"])
def api_simulate():
    file = request.files.get("file")
    if not file or file.filename == "":
        return jsonify({"error": "No file uploaded or filename is empty"}), 400

    uploaded_file_path = os.path.join(job_model.SIMULATION_DIR, file.filename)
    file.save(uploaded_file_path)

    job_id = job_model.create_job(uploaded_file_path)
    return jsonify({"job_id": job_id}), 202


@simu_views.route("/api/simulate_now", methods=["POST"])
def api_simulate_now():
    """
    /api/simulate_nowエンドポイント
    - Webから送られたSPICE文字列を受け取ってシミュレーションを実行
    - シミュレーション結果を取得して、解凍し、JFETクラスに渡す
    """
    # 1. AddModelFormのインスタンスを作成し、フォームデータをバリデート
    form = AddModelForm(request.form)

    # 2. POSTリクエストの場合、フォームのバリデーションを実行
    if request.method == 'POST':
        if form.validate():  # バリデーションが通った場合

            spice_string = form.spice_string.data
            # authorとcommentは使用しないが、バリデーションは行う
            author = form.author.data
            comment = form.comment.data

            try:
                # 3. SpiceStringの解析
                parser = SpiceModelParser()
                parsed_params = parser.parse(spice_string)

                device_name = parsed_params['device_name']
                device_type = parsed_params['device_type']
            except Exception as e:
                return jsonify({"error": f"Error parsing spice_string: {str(e)}"}), 400

            # 4. デバイスタイプを確認し、JFETクラスをインスタンス化
            if device_type in ['NJF', 'PJF']:
                model = JFET_IV_Characteristic(device_name, device_type, spice_string)
            else:
                return jsonify({"error": f"Unsupported device type: {device_type}"}), 400

            # 5. JFETクラスでネットリストを作成（build関数）
            try:
                netfile_path = model.build()
            except Exception as e:
                return jsonify({"error": f"Error building netlist: {str(e)}"}), 500

            # 6. シミュレーションサーバーに送信して結果を取得
            try:
                job_id = job_model.create_job(netfile_path)
            except Exception as e:
                return jsonify({"error": f"Error creating job: {str(e)}"}), 500

            # 7. シミュレーション結果を待機
            try:
                zip_data = job_model.get_job_result_with_notification(job_id)
                if not zip_data:
                    return jsonify({"error": "No simulation result received."}), 500
            except Exception as e:
                return jsonify({"error": f"Error waiting for job result: {str(e)}"}), 500

            # 8. ZIPファイルを解凍する
            try:
                extracted_files = file_extractor.extract(zip_data, job_id)
                if not extracted_files:
                    return jsonify({"error": "Failed to extract files from simulation result."}), 500
            except Exception as e:
                return jsonify({"error": f"Error extracting files: {str(e)}"}), 500

            # 9. .raw と .log ファイルをJFETクラスに渡す
            raw_file = extracted_files.get(".raw")
            log_file = extracted_files.get(".log")

            if raw_file and log_file:
                try:
                    model.load_results(raw_file, log_file)
                except Exception as e:
                    return jsonify({"error": f"Error loading results: {str(e)}"}), 500
            else:
                return jsonify({"error": "Missing .raw or .log files."}), 500

            # 10. プロットを生成
            try:
                plot_file = model.plot()
            except Exception as e:
                return jsonify({"error": f"Error generating plot: {str(e)}"}), 500

            # 11. 一時ファイルを消す
            file_extractor.cleanup(job_id)

            # 12. プロットの画像をウェブで表示するために返す
            try:
                with open(plot_file, 'rb') as f:
                    return send_file(
                        BytesIO(f.read()),
                        as_attachment=True,
                        download_name=f"{job_id}.png",
                        mimetype='image/png'
                    )
            except FileNotFoundError:
                return jsonify({"error": f"Plot file {plot_file} not found."}), 500
            except Exception as e:
                return jsonify({"error": f"Error sending plot file: {str(e)}"}), 500

        else:
            return jsonify({"error": "Invalid spice_string format or missing fields."}), 400


## test用
@simu_views.route("/build")
def build():
    return render_template("build.html", bokeh_json_data={})

@simu_views.route("/api/simulate_now2", methods=["POST"])
def api_simulate_now2():
    """
    /api/simulation_now2エンドポイント
    - Webから送られたSPICE文字列を受け取ってシミュレーションを実行
    - シミュレーション結果を取得して、解凍し、JFETクラスに渡す
    - 結果をJSONとして返す
    """
    # 1. AddModelFormのインスタンスを作成し、フォームデータをバリデート
    form = AddModelForm(request.form)

    # 2. POSTリクエストの場合、フォームのバリデーションを実行
    if request.method == 'POST':
        if form.validate():  # バリデーションが通った場合

            spice_string = form.spice_string.data
            # authorとcommentは使用しないが、バリデーションは行う
            author = form.author.data
            comment = form.comment.data

            try:
                # 3. SpiceStringの解析
                parser = SpiceModelParser()
                parsed_params = parser.parse(spice_string)

                device_name = parsed_params['device_name']
                device_type = parsed_params['device_type']
            except Exception as e:
                return jsonify({"error": f"Error parsing spice_string: {str(e)}"}), 400

            # 4. デバイスタイプを確認し、JFETクラスをインスタンス化
            if device_type in JFET_IV_Characteristic.VALID_TYPES:
                model = JFET_IV_Characteristic(device_name, device_type, spice_string)
            else:
                return jsonify({"error": f"Unsupported device type: {device_type}"}), 400

            # 5. JFETクラスでネットリストを作成（build関数）
            try:
                netfile_path = model.build()
            except Exception as e:
                return jsonify({"error": f"Error building netlist: {str(e)}"}), 500

            # 6. シミュレーションサーバーに送信して結果を取得
            try:
                job_id = job_model.create_job(netfile_path)
            except Exception as e:
                return jsonify({"error": f"Error creating job: {str(e)}"}), 500

            # 7. シミュレーション結果を待機
            try:
                zip_data = job_model.get_job_result_with_notification(job_id)
                if not zip_data:
                    return jsonify({"error": "No simulation result received."}), 500
            except Exception as e:
                return jsonify({"error": f"Error waiting for job result: {str(e)}"}), 500

            # 8. ZIPファイルを解凍する
            try:
                extracted_files = file_extractor.extract(zip_data, job_id)
                if not extracted_files:
                    return jsonify({"error": "Failed to extract files from simulation result."}), 500
            except Exception as e:
                return jsonify({"error": f"Error extracting files: {str(e)}"}), 500

            # 9. .raw と .log ファイルをJFETクラスに渡す
            raw_file = extracted_files.get(".raw")
            log_file = extracted_files.get(".log")

            if raw_file and log_file:
                try:
                    model.load_results(raw_file, log_file)
                except Exception as e:
                    return jsonify({"error": f"Error loading results: {str(e)}"}), 500
            else:
                return jsonify({"error": "Missing .raw or .log files."}), 500

            # 10. プロットを生成（JSONとして返す）
            try:
                json_data = model.plot(json=True)
                return jsonify(json_data)
            except Exception as e:
                return jsonify({"error": f"Error generating plot data: {str(e)}"}), 500

            # 11. 一時ファイルを消す
            file_extractor.cleanup(job_id)

        else:
            return jsonify({"error": "Invalid spice_string format or missing fields."}), 400



@simu_views.route('/start_all_simulations', methods=['GET'])
def start_all_simulations():
    # データベースからすべてのデバイスのdata_idを取得
    device_ids = get_all_device_ids()
    
    if not device_ids:
        return jsonify({"error": "No devices found for simulation"}), 404  # デバイスが見つからない場合のエラーハンドリング
    
    # 非同期タスクをキューに追加
    for data_id in device_ids:
        run_basic_performance_simulation.apply_async(args=[data_id])
        run_and_store_plots.apply_async(args=[data_id])
    
    return jsonify({"message": f"Simulation started for {len(device_ids)} devices!"}), 202


@simu_views.route('/para')
def parameter_test():
    parameters = [
        {"name": "Vto", "description": "しきい値", "unit": "V", "default": -2.0, "min": -5.0, "max": 5.0, "scale": 1},
        {"name": "Beta", "description": "トランスコンダクタンス・パラメータ", "unit": "μA/V^2", "default": 100, "min": 1, "max": 10000, "scale": 1E-6},
        {"name": "Lambda", "description": "チャンネル長調整パラメータ", "unit": "1/V", "default": 0, "min": 0, "max": 100, "scale": 0.01},
        {"name": "Rd", "description": "ドレインのオーミック抵抗", "unit": "Ω", "default": 0, "min": 0, "max": 1000, "scale": 1},
        {"name": "Rs", "description": "ソースのオーミック抵抗", "unit": "Ω", "default": 0, "min": 0, "max": 1000, "scale": 1},
        {"name": "Cgs", "description": "ゼロバイアスでのG-S接合容量", "unit": "pF", "default": 0, "min": 0, "max": 100, "scale": 1E-12},
        {"name": "Cgd", "description": "ゼロバイアスでのG-D接合容量", "unit": "pF", "default": 0, "min": 0, "max": 100, "scale": 1E-12},
        {"name": "Pb", "description": "ゲートの接合部電位", "unit": "V", "default": 1.0, "min": 0.5, "max": 2.0, "scale": 1},
        {"name": "m", "description": "ゲート接合部の濃度勾配係数", "unit": None, "default": 0.5, "min": 0, "max": 1.0, "scale": 1},
        {"name": "Is", "description": "ゲート接合部の飽和電流", "unit": "pA", "default": 0.01, "min": 0.001, "max": 10, "scale": 1E-12},
        {"name": "Tnom", "description": "パラメータ測定温度", "unit": "℃", "default": 27, "min": -50, "max": 150, "scale": 1},
        {"name": "VtoTc", "description": "しきい値電圧の温度係数", "unit": "mV/℃", "default": 0, "min": -100, "max": 100, "scale": 1E-3},
        {"name": "BetaTce", "description": "トランスコンダクタンス・パラメータの指数温度係数", "unit": "%/℃", "default": 0, "min": -100, "max": 100, "scale":1},
        {"name": "N", "description": "ゲート接合部の放射係数", "unit": None, "default": 1.0, "min": 0.5, "max": 2.0, "scale": 1},
        {"name": "Isr", "description": "ゲート接合部の再結合電流パラメータ", "unit": "pA", "default": 0, "min": 0, "max": 1000, "scale": 1E-12},
        {"name": "Nr", "description": "Isrの放射係数", "unit": None, "default": 2, "min": 1.0, "max": 3.0, "scale": 1},
        {"name": "alpha", "description": "イオン化係数", "unit": "1/V", "default": 0, "min": 0, "max": 100, "scale": 0.01},
        {"name": "Vk", "description": "イオン化屈曲点電圧", "unit": "V", "default": 0, "min": 0, "max": 5.0, "scale": 1},
        {"name": "Xti", "description": "飽和電流の温度係数", "unit": None, "default": 3, "min": 0, "max": 5.0, "scale": 1},
        {"name": "Fc", "description": "順バイアスでの空之層容量の係数", "unit": None, "default": 0.5, "min": 0, "max": 1.0, "scale": 1},
        {"name": "AF", "description": "フリッカ・ノイズ指数", "unit": None, "default": 1.0, "min": 0, "max": 2.0, "scale": 1},
        {"name": "KF", "description": "フリッカ・ノイズ係数", "unit": None, "default": 0, "min": 0, "max": 1, "scale": 1},
        {"name": "Nlev", "description": "ノイズ式セレクタ", "unit": None, "default": 0, "min": 0, "max": 3, "scale": 1},
        {"name": "Gdsnoi", "description": "niev=3の場合のショット・ノイズ係数", "unit": None, "default": 1.0, "min": 0, "max": 5.0, "scale": 1},
        {"name": "B", "description": "ドーピングのテール・パラメータ", "unit": None, "default": 1, "min": 0, "max": 2, "scale": 1},
        {"name": "mfg", "description": "メーカーの注釈", "unit": None, "default": "ACME Semi Ltd.", "min": None, "max": None, "scale": 1},
    ]

    return render_template('para.html', parameters=parameters)


@simu_views.route("/api/clear_jobs", methods=["POST"])
def clear_redis_jobs():
    """Redisのジョブをすべて削除"""
    result = job_model.clear_all_jobs()  # JobModelのメソッドを呼び出し
    return jsonify({"message": result})


@simu_views.route("/jobs")
def home():
    return render_template("jobs.html")
