import os  # 環境変数の取得
from celery import Celery  # Celeryタスクの作成

# データベース関連
from models.db_model import get_db_connection, update_basic_performance, get_data_by_id, save_image_to_db  # データベース操作

# シミュレーション関連
from simulation.jfet import JFET_IV_Characteristic, JFET_Vgs_Id_Characteristic, JFET_Gm_Vgs_Characteristic, JFET_Gm_Id_Characteristic, JFET_Basic_Performance


from simulation.file_extractor import FileExtractor  # ファイル抽出
from simulation.job_model import JobModel

import tracemalloc

# 環境変数からREDIS_HOSTを取得（デフォルトはlocalhost）
redis_host = os.getenv('REDIS_HOST', 'localhost')

file_extractor = FileExtractor()
job_model = JobModel(redis_host=redis_host)

# Celeryインスタンスを作成
celery = Celery(
    __name__,  # アプリケーション名
    broker=f'redis://{redis_host}:6379/1'  # RedisのURL、DB番号は1に設定
)

celery.conf.broker_connection_retry_on_startup = True  # 起動時の接続再試行を有効にする


def get_device_data(data_id):
    """
    データベースからデバイス情報を取得します。
    data_idに基づいてデバイス名、デバイスタイプ、SPICEネットリスト文字列を取得します。

    Args:
        data_id (int): データID

    Returns:
        tuple: (device_name, device_type, spice_string)
    """
    # データベースからデータを取得
    df = get_data_by_id(data_id)
    if df.empty:
        raise ValueError(f"data_id {data_id} に対応するデータが見つかりません。")
    
    # 必要な情報を抽出
    device_name = df.iloc[0]["device_name"]
    device_type = df.iloc[0]["device_type"]
    spice_string = df.iloc[0]["spice_string"]
    
    return device_name, device_type, spice_string


def run_simulation(data_id, characteristic_class):
    """
    指定された特性クラスに基づいてシミュレーションを実行し、画像を生成します。

    Args:
        data_id (int): データID
        characteristic_class (class): シミュレーションに使用する特性クラス

    Returns:
        model: シミュレーション結果を格納したモデル
    """
    # デバイス情報を取得
    device_name, device_type, spice_string = get_device_data(data_id)
    
    # # device_typeが特性クラスに対応していない場合、エラーを発生させる
    if device_type not in characteristic_class.VALID_TYPES:
        raise ValueError(f"無効なdevice_typeです。device_type: {device_type}")
    
    # モデルのインスタンスを作成
    model = characteristic_class(device_name, device_type, spice_string)

    # ネットリストを生成
    netfile_path = model.build()

    # リモートでシミュレーションを実行
    job_id = job_model.create_job(netfile_path)

    # ジョブが終わるのを待つ
    zip_data = job_model.get_job_result_with_notification(job_id)

    if not zip_data:
        raise JobError(f"シミュレーションが失敗しました。{characteristic_class.__name__}, {device_name}")
    
    # シミュレーション結果を抽出
    extracted_files = file_extractor.extract(zip_data, job_id)

    # 結果ファイルを取得
    raw_file = extracted_files.get(".raw")
    log_file = extracted_files.get(".log")
    if raw_file and log_file:
        model.load_results(raw_file, log_file)

    return model


@celery.task
def run_basic_performance_simulation(data_id):
    """
    非同期でシミュレーションを実行し、結果をデータベースに登録します。

    Args:
        data_id (int): データID

    Returns:
        dict: 実行結果
    """
    try:
        # シミュレーションを実行
        model = run_simulation(data_id, JFET_Basic_Performance)

        # 結果を解析
        result = model.get_basic_performance()

        # 必要なパラメータを抽出
        idss = result.get('id')
        gm = result.get('gm')
        cgs = result.get('cgs')
        cgd = result.get('cgd')

        # 結果をデータベースに追加または更新
        update_basic_performance(data_id, idss, gm, cgs, cgd)

        return {"status": "success", "data_id": data_id}

    except Exception as e:
        # エラー処理
        return {"status": "error", "message": f"Error: {str(e)}"}


@celery.task
def run_and_store_plots(data_id):
    """
    非同期でJFETの特性をシミュレーションし、生成した画像をデータベースに登録します。
    """

    

    try:
        tracemalloc.start()
        # シミュレーションと画像登録をまとめて行う
        characteristic_models = [
            JFET_IV_Characteristic,
            JFET_Vgs_Id_Characteristic,
            JFET_Gm_Vgs_Characteristic,
            JFET_Gm_Id_Characteristic
        ]

        
        for characteristic_class in characteristic_models:
            model = run_simulation(data_id, characteristic_class)
            image_path = model.plot()  # 画像生成メソッド

            # simulation_name プロパティを使用して画像タイプを決定
            image_type = model.simulation_name

            del model

            # 画像をデータベースに登録
            with open(image_path, 'rb') as image_file:
                save_image_to_db(data_id, image_file, image_type, 'png')

        tracemalloc.stop()

        return {"status": "success", "data_id": data_id}

    except Exception as e:
        # エラー処理
        return {"status": "error", "message": f"Error: {str(e)}"}


