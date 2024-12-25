@celery.task
def run_basic_performance_simulation(data_id):
    """
    非同期でシミュレーションを実行し、結果をデータベースに登録します。
    """
    try:
        # 1. データベースからdata_idに対応するデータを取得
        df = get_data_by_id(data_id)
        if df.empty:
            raise ValueError(f"data_id {data_id} に対応するデータが見つかりません。")

        # データベースから必要な情報を取得
        device_name = df.iloc[0]["device_name"]
        device_type = df.iloc[0]["device_type"]
        spice_string = df.iloc[0]["spice_string"]

        # 2. device_typeがNJFまたはPJFでない場合、エラーを発生させる
        if device_type not in ["NJF", "PJF"]:
            raise ValueError(f"無効なdevice_typeです。device_type: {device_type}")

        # 3. JFET_Basic_Performanceのインスタンスを作成
        model = JFET_Basic_Performance(device_name, device_type, spice_string)

        # 4. ネットリストを生成
        netfile_path = model.build()

        # 5. シミュレーションを実行し、結果を取得
        job_id = job_model.create_job(netfile_path)
        zip_data = job_model.get_job_result_with_notification(job_id)
        extracted_files = file_extractor.extract(zip_data, job_id)

        raw_file = extracted_files.get(".raw")
        log_file = extracted_files.get(".log")

        if raw_file and log_file:
            model.load_results(raw_file, log_file)

        # 6. 結果を解析
        result = model.get_basic_performance()
        print(result)

        # 7. 必要なパラメータを抽出
        idss = result.get('id')
        gm = result.get('gm')
        cgs = result.get('cgs')
        cgd = result.get('cgd')

        # 8. 結果をデータベースに追加または更新
        update_basic_performance(data_id, idss, gm, cgs, cgd)

        return {"status": "success", "data_id": data_id}

    except Exception as e:
        # エラー処理
        return {"status": "error", "message": str(e)}
