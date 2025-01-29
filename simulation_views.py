import os
import json
from io import BytesIO
from flask import Flask, Blueprint, request, send_file, jsonify, render_template, redirect, url_for, flash
import pandas as pd

# 自作モジュールのインポート
from models.db_model import (
    get_all_device_ids,
    add_experiment_data,
    search_data,
    get_experiment_data_by_id_or_data_id,
    get_experiment_data
)

from simulation.job_model import JobModel
from simulation.file_extractor import FileExtractor
from simulation.jfet import JFET_IV_Characteristic, JFET_Vgs_Id_Characteristic, JFET_Gm_Vgs_Characteristic, JFET_Gm_Id_Characteristic
from client.spice_model_parser import SpiceModelParser
from forms import AddModelForm

from tasks import run_basic_performance_simulation, run_and_store_plots

# Blueprintの定義
simu_views = Blueprint('simu_views', __name__)

# Redisホストの設定
redis_host = os.getenv("REDIS_HOST", "localhost")  # デフォルトはlocalhost

# Zipファイル用
file_extractor = FileExtractor()

# JobModelのインスタンスを作成
job_model = JobModel(redis_host=redis_host)


def get_template_name(base_template):
    """ブラウザの言語設定に基づいてテンプレートを選択"""
    lang = request.accept_languages.best_match(['en', 'ja']) or 'en'
    
    if lang == 'ja':
        return base_template.replace('.html', '_ja.html')
    
    return base_template


@simu_views.errorhandler(413)
def request_entity_too_large(error):
    """ファイルサイズ超過エラーのハンドリング"""
    return jsonify({"error": "File size exceeds the 1MB limit"}), 413


@simu_views.route("/api/simulations", methods=["GET"])
def get_simulations_api():
    jobs = job_model.get_all_jobs()
    return jsonify({
        job_id: {
            "status": job["status"],
            "error": job.get("error", None)
        }
        for job_id, job in jobs.items()
    })


@simu_views.route("/api/simulations/<job_id>", methods=["GET"])
def get_simulation_status_api(job_id):
    job_data = job_model.get_job_meta(job_id)
    if job_data is None:
        return jsonify({"error": f"Job with ID {job_id} not found."}), 404
    return jsonify({"job_id": job_id, "status": job_data.get("status", "unknown")})


@simu_views.route("/api/simulations/<job_id>/result", methods=["GET"])
def get_simulation_result_api(job_id):
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
def run_simulate_api():
    file = request.files.get("file")
    if not file or file.filename == "":
        return jsonify({"error": "No file uploaded or filename is empty"}), 400

    uploaded_file_path = os.path.join(job_model.SIMULATION_DIR, file.filename)
    file.save(uploaded_file_path)

    job_id = job_model.create_job(uploaded_file_path)
    return jsonify({"job_id": job_id}), 202


@simu_views.route("/api/simulate_now/<output_format>", methods=["POST"])
def run_simulate_now_api(output_format):
    """
    /api/simulate_now/<output_format>エンドポイント
    - output_formatが'image'の場合は画像を返す
    - output_formatが'json'の場合はJSONを返す
    """
    # ステップ 1: フォームデータのバリデーション
    form = AddModelForm(request.form)
    if not (request.method == 'POST' and form.validate()):
        return jsonify({"error": "Invalid spice_string format or missing fields."}), 400

    spice_string = form.spice_string.data
    measurement_data_id = request.form.get('measurement_data_id', None)  # ここで取得
    simulation_name = request.form.get('simulation_name', 'iv')
    
    if measurement_data_id == 'None':
        measurement_data_id = None  # 'None'が選ばれた場合はNoneに変換
    
    measurement_data = None

    if measurement_data_id:
        # 実験データを取得
        experiment_data_df = get_experiment_data_by_id_or_data_id(measurement_data_id, by_data_id=False)
        data_dict = experiment_data_df['data'].iloc[0]  # 最初の行のデータを取得
        data_json_str = json.dumps(data_dict)
        df = pd.read_json(data_json_str, orient='split')
        measurement_data = {
            "x": df.iloc[:, 0].tolist(),  # Vdsをxに
            "y": df.iloc[:, 1].tolist()   # Idをyに
        }

    # ステップ 2: Spice文字列の解析
    try:
        parser = SpiceModelParser()
        parsed_params = parser.parse(spice_string)
        device_name = parsed_params['device_name']
        device_type = parsed_params['device_type']
    except Exception as e:
        return jsonify({"error": f"Error parsing spice_string: {str(e)}"}), 400

    # ステップ 3: デバイスタイプの確認とモデルインスタンスの生成
    if device_type not in JFET_IV_Characteristic.VALID_TYPES:
        return jsonify({"error": f"Unsupported device type: {device_type}"}), 400

    # シミュレーションの種類に応じてモデルを選択
    if simulation_name == 'iv':
        model = JFET_IV_Characteristic(device_name, device_type, spice_string)
        # model.update_config("VGS_STEP", 0.05)
        # model.update_config("VDS_ABSMAX", 5)
    elif simulation_name == 'vgs_id':
        model = JFET_Vgs_Id_Characteristic(device_name, device_type, spice_string)
        # model.update_config("VGS_ABSMAX", 0.7)
    elif simulation_name == 'gm_vgs':
        model = JFET_Gm_Vgs_Characteristic(device_name, device_type, spice_string)
        # model.update_config("VDS_ABS", 10)
    elif simulation_name == 'gm_id':
        model = JFET_Gm_Id_Characteristic(device_name, device_type, spice_string)
    else:
        return jsonify({"error": f"Unsupported simulation type: {simulation_name}"}), 400


    # シミュレーション設定
    configs = model.show_default_config()

    for key, default_value in configs.items():
        # request.form.get()で、フォームから取得した値があればそれを使い、なければdefault_valueを使う
        value = request.form.get(key, default_value)  # デフォルト値を設定
        
        # valueを数値に変換（デフォルト値も数値に変換して比較）
        try:
            value = float(value)  # 文字列を数値に変換
            default_value = float(default_value)  # デフォルト値も数値に変換
        except ValueError:
            pass  # 数値に変換できない場合はそのまま文字列として扱う

        if value != default_value:  # 値が異なる場合のみ処理
            print(f"Simulation Config Set {key} -> {value}, default: {default_value}")
            model.update_config(key, value)  # モデルの設定を更新


    # ステップ 4: シミュレーション実行と結果取得
    try:
        netfile_path = model.build()  # ネットリストの作成
        job_id = job_model.create_job(netfile_path)  # ジョブIDを生成
        zip_data = job_model.get_job_result_with_notification(job_id)  # 結果を取得
        extracted_files = file_extractor.extract(zip_data, job_id)  # ファイルを解凍

        raw_file = extracted_files.get(".raw")
        log_file = extracted_files.get(".log")

        if not raw_file or not log_file:
            return jsonify({"error": "Missing .raw or .log files."}), 500

        model.load_results(raw_file, log_file)  # 結果をモデルにロード
    except Exception as e:
        return jsonify({"error": f"Simulation error: {str(e)}"}), 500

    # ステップ 5: 応答形式の確認 (画像またはJSON)
    if output_format == 'image':
        # ステップ 6: 画像の生成と送信
        try:
            plot_file = model.plot()
            with open(plot_file, 'rb') as f:
                return send_file(
                    BytesIO(f.read()),
                    as_attachment=True,
                    download_name=f"{job_id}.png",
                    mimetype='image/png'
                )
        except Exception as e:
            return jsonify({"error": f"Error generating plot image: {str(e)}"}), 500

    elif output_format == 'json':
        # ステップ 7: JSONデータの生成と送信
        try:
            json_data = model.plot(json=True, measurement_data=measurement_data)
            return jsonify(json_data)
        except Exception as e:
            return jsonify({"error": f"Error generating plot data: {str(e)}"}), 500

    # 無効な形式の場合のエラー
    return jsonify({"error": f"Unsupported output format: {output_format}"}), 400



## test用
@simu_views.route("/build")
def build_model_web():
    parameters = [
        {"name": "Vto", "description": "しきい値", "unit": "V", "default": -2.0, "min": -5.0, "max": 5.0, "prefix": ""},
        {"name": "Beta", "description": "トランスコンダクタンス・パラメータ", "unit": "μA/V^2", "default": 100, "min": 1, "max": 100000, "prefix": "u"},
        {"name": "Lambda", "description": "チャンネル長調整パラメータ", "unit": "1/V", "default": 0, "min": 0, "max": 100, "prefix": "m"},
        {"name": "Rd", "description": "ドレインのオーミック抵抗", "unit": "Ω", "default": 0, "min": 0, "max": 1000, "prefix": ""},
        {"name": "Rs", "description": "ソースのオーミック抵抗", "unit": "Ω", "default": 0, "min": 0, "max": 1000, "prefix": ""},
        {"name": "Cgs", "description": "ゼロバイアスでのG-S接合容量", "unit": "pF", "default": 0, "min": 0, "max": 100, "prefix": "p"},
        {"name": "Cgd", "description": "ゼロバイアスでのG-D接合容量", "unit": "pF", "default": 0, "min": 0, "max": 100, "prefix": "p"},
        {"name": "Pb", "description": "ゲートの接合部電位", "unit": "V", "default": 1.0, "min": 0.5, "max": 2.0, "prefix": ""},
        {"name": "m", "description": "ゲート接合部の濃度勾配係数", "unit": None, "default": 0.5, "min": 0, "max": 1.0, "prefix": ""},
        {"name": "Is", "description": "ゲート接合部の飽和電流", "unit": "pA", "default": 0.01, "min": 0.001, "max": 100, "prefix": "p"},
        {"name": "Tnom", "description": "パラメータ測定温度", "unit": "℃", "default": 27, "min": -50, "max": 150, "prefix": ""},
        {"name": "VtoTc", "description": "しきい値電圧の温度係数", "unit": "mV/℃", "default": 0, "min": -100, "max": 100, "prefix": "m"},
        {"name": "BetaTce", "description": "トランスコンダクタンス・パラメータの指数温度係数", "unit": "%/℃", "default": 0, "min": -100, "max": 100, "prefix": ""},
        {"name": "N", "description": "ゲート接合部の放射係数", "unit": None, "default": 1.0, "min": 0.5, "max": 2.0, "prefix": ""},
        {"name": "Isr", "description": "ゲート接合部の再結合電流パラメータ", "unit": "pA", "default": 0, "min": 0, "max": 1000, "prefix": "p"},
        {"name": "Nr", "description": "Isrの放射係数", "unit": None, "default": 2, "min": 1.0, "max": 3.0, "prefix": ""},
        {"name": "alpha", "description": "イオン化係数", "unit": "1/V", "default": 0, "min": 0, "max": 100, "prefix": "u"},
        {"name": "Vk", "description": "イオン化屈曲点電圧", "unit": "V", "default": 0, "min": 0, "max": 200.0, "prefix": ""},
        {"name": "Xti", "description": "飽和電流の温度係数", "unit": None, "default": 3, "min": 0, "max": 5.0, "prefix": ""},
        {"name": "Fc", "description": "順バイアスでの空之層容量の係数", "unit": None, "default": 0.5, "min": 0, "max": 1.0, "prefix": ""},
        {"name": "AF", "description": "フリッカ・ノイズ指数", "unit": None, "default": 1.0, "min": 0, "max": 2.0, "prefix": ""},
        {"name": "KF", "description": "フリッカ・ノイズ係数", "unit": None, "default": 0, "min": 0, "max": 1, "prefix": ""},
        {"name": "Nlev", "description": "ノイズ式セレクタ", "unit": None, "default": 0, "min": 0, "max": 3, "prefix": ""},
        {"name": "Gdsnoi", "description": "niev=3の場合のショット・ノイズ係数", "unit": None, "default": 1.0, "min": 0, "max": 5.0, "prefix": ""},
        {"name": "B", "description": "ドーピングのテール・パラメータ", "unit": None, "default": 1, "min": 0, "max": 2, "prefix": ""},
        {"name": "mfg", "description": "メーカーの注釈", "unit": None, "default": "", "min": None, "max": None, "prefix": ""},
    ]

    experiment_data = get_experiment_data(include_all=True, exclude_data=True).to_dict(orient='records')

    # クラスリスト
    characteristics = [
        JFET_IV_Characteristic,
        JFET_Vgs_Id_Characteristic,
        JFET_Gm_Vgs_Characteristic,
        JFET_Gm_Id_Characteristic,
    ]

    # 辞書生成
    simulation_configs = {
        char.get_simulation_name(): char.show_default_config()
        for char in characteristics
    }

    # device_typeが'NJF'または'PJF'のデバイスを検索
    device_types = ['NJF', 'PJF']
    devices_df = search_data(device_type=device_types)
    
    # データフレームをリスト形式に変換
    devices_list = devices_df.to_dict(orient='records')


    template_name = get_template_name('build_jfets.html')

    return render_template(
        template_name,
        parameters=parameters,
        experiment_data=experiment_data,
        devices_list=devices_list,
        simulation_configs=simulation_configs
    )


@simu_views.route('/start_all_simulations', methods=['GET'])
def run_all_simulations_web():
    # データベースからすべてのデバイスのdata_idを取得
    device_ids = get_all_device_ids()
    
    if not device_ids:
        return jsonify({"error": "No devices found for simulation"}), 404  # デバイスが見つからない場合のエラーハンドリング
    
    # 非同期タスクをキューに追加
    for data_id in device_ids:
        run_basic_performance_simulation.apply_async(args=[data_id])
        # run_and_store_plots.apply_async(args=[data_id])
    
    return jsonify({"message": f"Simulation started for {len(device_ids)} devices!"}), 202


@simu_views.route('/upload_csv', methods=['GET', 'POST'])
def upload_csv_web():

    if request.method == 'GET':
        # GETリクエストの場合、デバイスリストを取得
        devices = search_data()  # 必要に応じて検索条件を追加
        device_options = devices[['id', 'device_name', 'device_type']].drop_duplicates().to_dict(orient='records')
        template_name = get_template_name('upload_csv.html')
        return render_template(template_name, device_options=device_options)

    if request.method == 'POST':
        # フォームデータを受け取る
        selected_data_id = request.form.get('data_id')  # device_idを受け取る
        if request.form.get('new_device'):  # 新しいデバイスが選ばれた場合
            selected_data_id = None  # 新しいデバイスの場合はNoneを設定

        new_device_name = request.form.get('device_name')
        measurement_type = request.form.get('measurement_type', 'General')
        operator_name = request.form.get('operator_name', 'Unknown')
        status = request.form.get('status', 'raw')
        
        # CSVファイルが送信されているかチェック
        if 'file' not in request.files:
            flash("No file part", "error")
            return redirect(url_for('simu_views.upload_csv_web'))

        file = request.files['file']

        # ファイルが空でないかチェック
        if file.filename == '':
            flash("No selected file", "error")
            return redirect(url_for('simu_views.upload_csv_web'))

        if not file.filename.endswith('.csv'):
            flash("Invalid file type. Only CSV files are allowed.", "error")
            return redirect(url_for('simu_views.upload_csv_web'))

        # CSVファイルをPandas DataFrameとして読み込む
        try:
            df = pd.read_csv(file)
        except Exception as e:
            flash(f"Failed to read CSV: {str(e)}", "error")
            return redirect(url_for('simu_views.upload_csv_web'))

        # CSVの内容をそのままJSONに変換
        data_json = df.to_json(orient='split')  # 各行を辞書形式に変換してリストにする

        # 実験データをデータベースに追加
        new_id = add_experiment_data(selected_data_id, new_device_name, measurement_type, data_json, operator_name, status)

        if new_id is None:
            flash("Failed to add experiment data to the database", "error")
            return redirect(url_for('simu_views.upload_csv_web'))

        # 成功した場合のフラッシュメッセージ
        flash("Experiment data successfully added!", "success")
        return redirect(url_for('simu_views.upload_csv_web'))


@simu_views.route("/api/clear_jobs", methods=["POST"])
def clear_jobs_api():
    """Redisのジョブをすべて削除"""
    result = job_model.clear_all_jobs()  # JobModelのメソッドを呼び出し
    return jsonify({"message": result})


@simu_views.route("/jobs")
def get_jobs_web():
    return render_template("jobs.html")
