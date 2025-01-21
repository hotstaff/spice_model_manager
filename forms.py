import re
import logging

from flask import flash, redirect, url_for
from wtforms import Form, StringField, FileField
from wtforms.validators import DataRequired, Length, Regexp, Optional, InputRequired

from client.spice_model_parser import SpiceModelParser

class SearchForm(Form):
    # 空白を許容するためにOptional()を使用
    device_name = StringField(
        'Device Name', 
        [Length(max=100), 
         Regexp('^[a-zA-Z0-9_ ]+$', message="Invalid characters are included"),
         Optional()],
        default=''  # デフォルト値を空文字列に設定
    )
    device_type = StringField(
        'Device Type', 
        [Length(max=100),
         Optional()],
        default=''  # デフォルト値を空文字列に設定
    )

class AddModelForm(Form):
    # spice_string, author, comment の3つのフィールドを受け取る
    spice_string = StringField('Spice String', 
                               [DataRequired(), 
                                Length(max=1000)])  # 最大長は適宜調整
    author = StringField('Author', 
                         [Length(max=16)], 
                         default="Anonymous")  # デフォルト値を"Anonymous"に設定
    comment = StringField('Comment', 
                          [Length(max=100)], 
                          default="")  # デフォルト値を""に設定

    def validate_spice_string(self, field):
        # Spiceモデル文字列をパースして、デバイス名とデバイスタイプを取得
        try:
            # SpiceModelParserのインスタンス化
            parser = SpiceModelParser()
            params = parser.parse(field.data, convert_units=True)

            # device_name と device_type を取得してバリデーション
            device_name = params['device_name']
            device_type = params['device_type']

            # デバイス名とデバイスタイプのバリデーション
            if not device_name.isalnum():
                flash('Device name must be alphanumeric.', 'error')
                logging.warning(f"Invalid device name: {device_name}")
                return redirect(url_for('model_views.add_new_model'))  # エラーページにリダイレクト
            if not device_type.isalnum():
                flash('Device type must be alphanumeric.', 'error')
                logging.warning(f"Invalid device type: {device_type}")
                return redirect(url_for('model_views.add_new_model'))  # エラーページにリダイレクト

        except (SyntaxError, KeyError, ValueError) as e:
            # 共通のエラーハンドリング
            error_message = f"{e.__class__.__name__}: {str(e)}"
            flash(f"Failed to add model: {error_message}", 'error')
            logging.warning(f"Error with input: {field.data}")
            logging.warning(f"{error_message}")
            return redirect(url_for('model_views.add_new_model'))  # エラーページにリダイレクト

        except Exception as e:
            # 予期しないエラー
            flash('An unexpected error occurred during parsing.', 'error')
            logging.warning(f"Unexpected error with input: {field.data}")
            logging.warning(f"Unexpected error: {str(e)}")
            return redirect(url_for('model_views.add_new_model'))  # エラーページにリダイレクト

    def validate_author(self, field):
        # 英数字とスペースのみ許可
        if not re.match(r'^[a-zA-Z0-9 ]*$', field.data):
            error_message = 'Author must contain only letters, numbers, and spaces.'
            flash(error_message, 'error')
            logging.warning(f"Invalid author input: {field.data} - {error_message}")
            return  # バリデーションエラーとして処理を終了

        # HTMLタグを無害化（タグを除去）
        field.data = re.sub(r'<.*?>', '', field.data)

        if not field.data:  # 空文字が送られた場合
            field.data = "Anonymous"  # デフォルト値を設定

    def validate_comment(self, field):
        # 特殊文字やHTMLタグを除去
        field.data = re.sub(r'<.*?>', '', field.data)  # HTMLタグの除去
        field.data = re.sub(r'[<>]', '', field.data)  # 特殊文字の除去

        # 最大長の確認
        if len(field.data) > 100:
            error_message = 'Comment is too long. Max length is 100 characters.'
            flash(error_message, 'error')
            logging.warning(f"Invalid comment input: {field.data} - {error_message}")
            return  # バリデーションエラーとして処理を終了


class CsvUploadForm(Form):
    # CSVファイルのアップロードフィールド
    csv_file = FileField(
        'CSV File', 
        [InputRequired(message="CSV file is required")]
    )
    
    # デバイス名（オプション）
    device_name = StringField(
        'Device Name', 
        [Length(max=100), Optional()],
        default=''  # デフォルト値を空文字列に設定
    )
    
    # オペレーター名（オプション）
    operator_name = StringField(
        'Operator Name',
        [Length(max=100), Optional()],
        default=''  # デフォルト値を空文字列に設定
    )
