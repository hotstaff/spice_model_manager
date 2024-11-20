# Standard library imports
import os
import logging

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
from wtforms import Form, StringField
from wtforms.validators import DataRequired, Length, Regexp, Optional

# Local imports
from models.db_model import (
    get_all_data,
    get_data_by_id,
    add_data,
    update_data,
    delete_data,
    search_data,
    save_image_to_db,
    get_image_from_db
)
from client.spice_model_parser import SpiceModelParser

# Logging configuration
logging.basicConfig(level=logging.INFO)

# Forms
class SearchForm(Form):
    device_name = StringField('Device Name', 
                              [Length(max=100), 
                               Regexp('^[a-zA-Z0-9_ ]+$', message="Invalid characters are included"),
                               Optional()])
    device_type = StringField('Device Type', 
                              [Length(max=100),
                               Optional()])

class AddModelForm(Form):
    spice_string = StringField('Spice String', 
                               [DataRequired(), 
                                Length(max=5000)])  # Adjust max length as needed

    def validate_spice_string(self, field):
        try:
            parser = SpiceModelParser()
            params = parser.parse(field.data, convert_units=True)

            device_name = params['device_name']
            device_type = params['device_type']

            if not device_name.isalnum() or not device_type.isalnum():
                raise ValueError('Device name and type must be alphanumeric.')
        except (SyntaxError, KeyError, ValueError) as e:
            logging.warning(f"Validation error: {str(e)}, input: {field.data}")
            flash(str(e), 'error')
            return redirect(url_for('model_views.add_new_model'))
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}, input: {field.data}")
            flash('An unexpected error occurred during parsing.', 'error')
            return redirect(url_for('model_views.add_new_model'))

# Blueprint
model_views = Blueprint('model_views', __name__)

# API Routes
@model_views.route('/api/models', methods=['GET'])
def get_models():
    form = SearchForm(request.args)
    if form.validate():
        device_name = form.device_name.data
        device_type = form.device_type.data
        df = search_data(device_name=device_name, device_type=device_type)
        return jsonify(df.to_dict(orient="records")), 200
    return abort(400, description="Invalid data")

@model_views.route('/api/models/<int:model_id>', methods=['GET'])
def get_model_by_id(model_id):
    df = get_data_by_id(model_id)
    if df.empty:
        return abort(404, description="Model not found")
    return jsonify(df.to_dict(orient="records")[0]), 200

@model_views.route('/api/models', methods=['POST'])
def add_model():
    if not request.json or not all(k in request.json for k in ('device_name', 'device_type', 'spice_string')):
        return abort(400, description="Invalid data")
    add_data(request.json['device_name'], request.json['device_type'], request.json['spice_string'])
    return jsonify({"message": "Model added successfully"}), 201

@model_views.route('/api/models/<int:model_id>', methods=['PUT'])
def update_model(model_id):
    if not request.json:
        return abort(400, description="Invalid data")
    if not update_data(model_id, request.json.get('device_name'), request.json.get('device_type'), request.json.get('spice_string')):
        return abort(404, description="Model not found")
    return jsonify({"message": "Model updated successfully"}), 200

@model_views.route('/api/models/<int:model_id>', methods=['DELETE'])
def delete_model(model_id):
    if not delete_data(model_id):
        return abort(404, description="Model not found")
    return jsonify({"message": "Model deleted successfully"}), 200

@model_views.route('/api/upload_image', methods=['POST'])
def upload_image():
    image_file = request.files.get('image')
    if not image_file or image_file.filename == '':
        return jsonify({"error": "Invalid image file"}), 400
    if image_file.content_type not in ['image/png', 'image/jpeg']:
        return jsonify({"error": "File must be a PNG or JPEG image"}), 400
    data_id = request.form.get('data_id')
    if not data_id.isdigit():
        return jsonify({"error": "data_id must be an integer"}), 400
    save_image_to_db(int(data_id), image_file, request.form.get('image_type', 'default'), 
                     'png' if image_file.content_type == 'image/png' else 'jpeg')
    return jsonify({"message": "Image uploaded successfully!"}), 200

@model_views.route('/get_image/<int:data_id>/<string:image_type>', methods=['GET'])
def get_image(data_id, image_type):
    image_data = get_image_from_db(data_id, image_type=image_type)
    if not image_data:
        return jsonify({"error": "Image not found"}), 404
    image_io, image_format, _ = image_data
    return send_file(image_io, mimetype=f'image/{image_format}', as_attachment=False)

# HTML Routes
@model_views.route('/models', methods=['GET'])
def list_models():
    form = SearchForm(request.args)
    if form.validate():
        device_name = form.device_name.data
        device_type = form.device_type.data
        models = search_data(device_name=device_name, device_type=device_type)
        return render_template(
            'index.html',
            models=models.to_dict(orient="records"),
            device_name=device_name,
            device_type=device_type
        )
    return "Invalid inputs", 400

@model_views.route('/models/add', methods=['GET', 'POST'])
def add_new_model():
    form = AddModelForm(request.form)
    if request.method == 'POST' and form.validate():
        try:
            parser = SpiceModelParser()
            params = parser.parse(form.spice_string.data)
            add_data(params['device_name'], params['device_type'], parser.format(params))
            flash('SPICE Model added successfully!', 'success')
            return redirect(url_for('home'))
        except Exception as e:
            flash(f"Failed to add model: {str(e)}", "error")
    return render_template('spice_model_add.html', form=form)

@model_views.route('/models/<int:model_id>', methods=['GET'])
def model_detail(model_id):
    model = get_data_by_id(model_id)
    if model.empty:
        return abort(404, description="Model not found")
    return render_template('model_detail.html', model=model.to_dict(orient="records")[0])

# Error Handlers
@model_views.errorhandler(404)
def not_found(error):
    return jsonify({"error": str(error)}), 404

@model_views.errorhandler(400)
def bad_request(error):
    return jsonify({"error": str(error)}), 400
