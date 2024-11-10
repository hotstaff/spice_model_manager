import os
from flask import Blueprint, request, jsonify, abort, render_template, send_file
from models.db_model import get_all_data, get_data_by_id, add_data, update_data, delete_data, search_data, save_image_to_db, get_image_from_db

from wtforms import Form, StringField
from wtforms.validators import DataRequired, Length, Regexp, Optional

class SearchForm(Form):
    # 空白を許容するためにOptional()を使用
    device_name = StringField('Device Name', 
                              [Length(max=100), 
                               Regexp('^[a-zA-Z0-9_ ]+$', message="Invalid characters are included"),
                               Optional()])
    device_type = StringField('Device Type', 
                              [Length(max=100),
                               Optional()])  # 空白も許容


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
def get_model_by_id(model_id):
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

# モデルの一覧をHTMLで表示
@model_views.route('/models', methods=['GET'])
def list_models():
    form = SearchForm(request.args)

    if form.validate():
        device_name = form.device_name.data
        device_type = form.device_type.data
        models = search_data(device_name=device_name, device_type=device_type)
        if device_name is None:
            device_name = ""

        if device_type is None:
            device_type = ""
        return render_template('index.html', models=models.to_dict(orient="records"), device_name=device_name, device_type=device_type)
    else:
        # バリデーションエラーが発生した場合
        return "There are invalid inputs", 400

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
        return jsonify({"message": "Image uploaded successfully!"}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to upload image: {str(e)}"}), 500

@model_views.route('/get_image/<int:data_id>', methods=['GET'])
def get_image(data_id):
    """Retrieve and return an image based on the specified data_id."""
    # Retrieve image data from the database
    image_data = get_image_from_db(data_id)

    if image_data is None:
        return jsonify({"error": "Image not found"}), 404
    
    image_io, image_format, image_type = image_data

    # Use send_file to return the image to the client
    return send_file(
        image_io, 
        mimetype=f'image/{image_format}', 
        as_attachment=True, 
        download_name=f'{image_type}_image.{image_format}'
    )


# モデルの詳細をHTMLで表示
@model_views.route('/models/<int:model_id>', methods=['GET'])
def model_detail(model_id):
    model = get_data_by_id(model_id)
    if model.empty:
        return abort(404, description="Model not found")
    return render_template('model_detail.html', model=model.to_dict(orient="records")[0])

# エラーハンドリング
@model_views.errorhandler(404)
def not_found(error):
    return jsonify({"error": str(error)}), 404

@model_views.errorhandler(400)
def bad_request(error):
    return jsonify({"error": str(error)}), 400
