import pytest
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_home_page(client):
    response = client.get('/')
    assert response.data == b"Welcome to the Spice Model Manager API!"

def test_get_models(client):
    response = client.get('/api/models')
    assert response.status_code == 200
    assert isinstance(response.json, list)  # JSONレスポンスがリストであることを確認

def test_add_model(client):
    response = client.post('/api/models', json={'column1': 'Test Model', 'column2': 'Test Data'})
    assert response.status_code == 201
    assert response.data == b"Model added successfully"

def test_get_model_by_id(client):
    # ここでは、既存のモデルIDを使う必要があります。データベースにサンプルデータを追加するか、事前に知っているIDを使用してください。
    model_id = 1
    response = client.get(f'/api/models/{model_id}')
    assert response.status_code == 200
    assert 'column1' in response.json  # モデルのデータが取得できていることを確認

def test_update_model(client):
    # ここでも、更新するモデルIDを指定する必要があります
    model_id = 1
    response = client.put(f'/api/models/{model_id}', json={'column1': 'Updated Model'})
    assert response.status_code == 200
    assert response.data == b"Model updated successfully"

def test_delete_model(client):
    # ここでも、削除するモデルIDを指定する必要があります
    model_id = 1
    response = client.delete(f'/api/models/{model_id}')
    assert response.status_code == 200
    assert response.data == b"Model deleted successfully"

def test_get_model_not_found(client):
    response = client.get('/api/models/9999')  # 存在しないモデルIDを使用
    assert response.status_code == 404

def test_add_model_invalid_data(client):
    response = client.post('/api/models', json={'column1': 'Test Model'})  # column2が欠けている
    assert response.status_code == 400

def test_update_model_not_found(client):
    model_id = 9999  # 存在しないID
    response = client.put(f'/api/models/{model_id}', json={'column1': 'Updated Model'})
    assert response.status_code == 404

def test_delete_model_not_found(client):
    model_id = 9999  # 存在しないID
    response = client.delete(f'/api/models/{model_id}')
    assert response.status_code == 404
