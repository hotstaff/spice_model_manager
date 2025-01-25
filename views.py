# Standard library imports
import os
import logging
import hashlib

# Third-party imports
from flask import (
    Blueprint,
    request,
    jsonify,
    flash,
    abort,
    render_template,
    send_file,
    redirect,
    url_for
)

# Local imports
from models.db_model import (
    get_all_data,
    get_data_by_id,
    add_data,
    update_data,
    delete_data,
    search_data,
    save_image_to_db,
    get_image_from_db,
    update_simulation_done,
    get_basic_performance_by_data_id
)
from client.spice_model_parser import SpiceModelParser

# Form Validates
from forms import AddModelForm, SearchForm


from tasks import run_basic_performance_simulation, run_and_store_plots

logging.basicConfig(level=logging.INFO)


CACHE_DIR = '/tmp/image_cache'  # Renderの一時ディスクのパス

# キャッシュディレクトリがなければ作成
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

def get_image_cache_path(data_id, image_type):
    """キャッシュされた画像ファイルのパスを決定"""
    # data_idとimage_typeを使って、キャッシュのパスを作成
    hash_key = hashlib.md5(f"{data_id}_{image_type}".encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"{hash_key}.cache")


def get_template_name(base_template):
    """ブラウザの言語設定に基づいてテンプレートを選択"""
    lang = request.accept_languages.best_match(['en', 'ja']) or 'en'
    
    if lang == 'ja':
        return base_template.replace('.html', '_ja.html')
    
    return base_template

model_views = Blueprint('model_views', __name__)

# 全モデルデータを取得するAPI
@model_views.route('/api/models', methods=['GET'])
def get_models():
    form = SearchForm(request.args)

    if form.validate():
        device_name = form.device_name.data
        device_type = form.device_type.data
        df = search_data(device_name=device_name, device_type=device_type)
    else:
        return abort(400, description="Invalid data")
    
    return jsonify(df.to_dict(orient="records")), 200

# 特定のIDのモデルデータを取得するAPI
@model_views.route('/api/models/<int:model_id>', methods=['GET'])
def get_model(model_id):
    df = get_data_by_id(model_id)
    if df.empty:
        return abort(404, description="Model not found")
    return jsonify(df.to_dict(orient="records")[0]), 200

# データを新規追加するAPI
@model_views.route('/api/models', methods=['POST'])
def add_model():
    if not request.json:
        return abort(400, description="Invalid data")
    
    # デバッグのために受け取ったデータをログ出力
    print("Received data:", request.json)

    if 'device_name' not in request.json or 'device_type' not in request.json or 'spice_string' not in request.json:
        return abort(400, description="Invalid data")
    
    device_name = request.json['device_name']
    device_type = request.json['device_type']
    spice_string = request.json['spice_string']
    
    add_data(device_name, device_type, spice_string)
    return jsonify({"message": "Model added successfully"}), 201

# データを更新するAPI
@model_views.route('/api/models/<int:model_id>', methods=['PUT'])
def update_model(model_id):
    if not request.json:
        return abort(400, description="Invalid data")
    
    device_name = request.json.get('device_name')
    device_type = request.json.get('device_type')
    spice_string = request.json.get('spice_string')
    
    if not update_data(model_id, device_name, device_type, spice_string):
        return abort(404, description="Model not found")
    
    return jsonify({"message": "Model updated successfully"}), 200

# データを削除するAPI
@model_views.route('/api/models/<int:model_id>', methods=['DELETE'])
def delete_model(model_id):
    if not delete_data(model_id):
        return abort(404, description="Model not found")
    
    return jsonify({"message": "Model deleted successfully"}), 200

#### model api


@model_views.route('/api/upload_image', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({"error": "No image file part"}), 400
    
    image_file = request.files['image']
    
    if image_file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # 画像ファイルがpngまたはjpegであることを確認
    if image_file.content_type not in ['image/png', 'image/jpeg']:
        return jsonify({"error": "File must be a PNG or JPEG image"}), 400
    
    # ユーザー指定のimage_typeとimage_formatをフォームから取得
    image_type = request.form.get('image_type', 'default')  # 'default'をデフォルトに設定
    image_format = 'png' if image_file.content_type == 'image/png' else 'jpeg'
    
    data_id = request.form.get('data_id')  # データIDをフォームから取得
    if not data_id:
        return jsonify({"error": "No data_id provided"}), 400
    
    try:
        data_id = int(data_id)
    except ValueError:
        return jsonify({"error": "data_id must be an integer"}), 400

    # 画像データをデータベースに保存
    try:
        save_image_to_db(data_id, image_file, image_type, image_format)
        # simulation_doneフラグを変える
        update_simulation_done(data_id)
        return jsonify({"message": "Image uploaded successfully!"}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to upload image: {str(e)}"}), 500

@model_views.route('/get_image/<int:data_id>/<string:image_type>', methods=['GET'])
def get_image(data_id, image_type):
    """Retrieve and return an image based on data_id and image_type."""
    # キャッシュパスの取得
    cache_path = get_image_cache_path(data_id, image_type)

    # キャッシュが存在する場合は、それを返す
    if os.path.exists(cache_path):
        return send_file(
            cache_path,
            mimetype=f'image/{image_type}',
            as_attachment=False
        )
    
    # キャッシュが存在しない場合は、データベースから画像を取得
    result = get_image_from_db(data_id, image_type)

    if result is not None:
        image_data, image_format, _ = result
    else:
        return jsonify({"error": "Image not found"}), 404
    
    # データベースから取得した画像データをキャッシュに保存
    with open(cache_path, 'wb') as f:
        f.write(image_data.getvalue())

    # 画像を返す
    return send_file(
        image_data,
        mimetype=f'image/{image_format}',
        as_attachment=False
    )


# モデルの一覧をHTMLで表示
@model_views.route('/models', methods=['GET'])
def list_models():
    form = SearchForm(request.args)

    if form.validate():
        device_name = form.device_name.data
        device_type = form.device_type.data
        models = search_data(device_name=device_name, device_type=device_type)

        models_count = len(models)
        items_per_page = 100
        pages = (models_count + items_per_page - 1) // items_per_page
        
        # モデルがない場合でもpagesとpageを1に設定
        if models_count == 0:
            pages = 1
            page = 1
        else:
            page = int(request.args.get('page', 1))

        # ページ数の異常を検知
        if page < 1 or page > pages:
            page = 1  # ページが不正なら1に設定
        
        start_index = (page - 1) * items_per_page
        end_index = start_index + items_per_page
        page_models = models[start_index:end_index]

        template_name = get_template_name('models.html')
        
        return render_template(
            template_name,
            models=page_models.to_dict(orient="records"),
            device_name=device_name,
            device_type=device_type,
            page=page,
            total_pages=pages
        )
    else:
        return "There are invalid inputs", 400


# モデルの詳細をHTMLで表示
@model_views.route('/models/<int:model_id>', methods=['GET'])
def model_detail(model_id):
    # data テーブルからモデル情報を取得
    model = get_data_by_id(model_id)
    if model.empty:
        return abort(404, description="Model not found")

    # basic_performance テーブルから関連するデータを取得
    basic_performance = get_basic_performance_by_data_id(model_id)
    if basic_performance.empty:
        basic_performance_data = None
    else:
        basic_performance_data = basic_performance.to_dict(orient="records")[0]
    
    # テンプレート名を取得
    template_name = get_template_name('model_detail.html')
    
    # model と basic_performance のデータをテンプレートに渡す
    return render_template(template_name,
        model=model.to_dict(orient="records")[0],
        basic_performance=basic_performance_data)


@model_views.route('/models/add', methods=['GET', 'POST'])
def add_new_model():
    form = AddModelForm(request.form)

    if request.method == 'POST':
        if form.validate():
            spice_string = form.spice_string.data
            author = form.author.data
            comment = form.comment.data

            try:
                # SpiceStringの解析
                parser = SpiceModelParser()
                parsed_params = parser.parse(spice_string)

                device_name = parsed_params['device_name']
                device_type = parsed_params['device_type']

                # データベースに保存
                result = add_data(device_name, device_type, parser.format(parsed_params), author, comment)

                if result:
                    # 登録成功
                    flash('SPICE Model added successfully!', 'success')

                    # 非同期タスクでプロット生成を実行
                    data_id = result  # add_dataが返すIDを使用
                    run_and_store_plots.apply_async(args=[data_id])
                    run_basic_performance_simulation.apply_async(args=[data_id])
                    
                    return redirect(url_for('home'))  # 登録成功後、トップページにリダイレクト

                else:
                    # デバイス名が重複している場合
                    flash(f"Device '{device_name}' already exists.", "error")
                    return redirect(url_for('model_views.add_new_model'))  # 失敗後リダイレクト

            except Exception as e:
                flash(f"Failed to add model: {str(e)}", "error")
                return redirect(url_for('model_views.add_new_model'))  # 失敗後リダイレクト

        else:
            # バリデーションエラーがあればエラーメッセージを返す
            flash("Validation failed. Please check your input.", "error")
            return redirect(url_for('model_views.add_new_model'))  # 失敗後リダイレクト

    # GETリクエストの場合、フォームを表示
    template_name = get_template_name('spice_model_add.html')
    return render_template(template_name, form=form)

@model_views.route('/api/parse', methods=['POST'])
def parse_spice_model():
    """
    Parse a SPICE model string and return the parsed parameters.
    """
    try:
        # リクエストからSPICE文字列を取得
        spice_string = request.json.get('spice_string', None)
        
        if not spice_string:
            return jsonify({"error": "Missing 'spice_string' in request"}), 400

        # SPICE文字列の解析
        parser = SpiceModelParser()
        parsed_params = parser.parse(spice_string, convert_units=True)

        # 成功時に解析結果を返す
        return jsonify({"parsed_params": parsed_params}), 200

    except Exception as e:
        # エラー時にエラーメッセージを返す
        return jsonify({"error": str(e)}), 500


# エラーハンドリング
@model_views.errorhandler(404)
def not_found(error):
    return jsonify({"error": str(error)}), 404

@model_views.errorhandler(400)
def bad_request(error):
    return jsonify({"error": str(error)}), 400
