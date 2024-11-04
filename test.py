import requests

BASE_URL = 'https://spice-model-manager.onrender.com/data'

def test_get_all_data():
    response = requests.get(BASE_URL)
    print("GET all data:")
    print(response.json())

def test_add_data():
    new_data = {
        'column1': 'Test Data 1',
        'column2': 'Some value'
    }
    response = requests.post(BASE_URL, json=new_data)
    print("POST add data:")
    print(response.text)

def test_get_data_by_id(data_id):
    response = requests.get(f'{BASE_URL}/{data_id}')
    print(f"GET data by ID ({data_id}):")
    print(response.json())

def test_update_data(data_id):
    updated_data = {
        'column1': 'Updated Data',
        'column2': 'Updated value'
    }
    response = requests.put(f'{BASE_URL}/{data_id}', json=updated_data)
    print(f"PUT update data ID ({data_id}):")
    print(response.text)

def test_delete_data(data_id):
    response = requests.delete(f'{BASE_URL}/{data_id}')
    print(f"DELETE data ID ({data_id}):")
    print(response.text)

if __name__ == '__main__':
    # テストの実行
    test_get_all_data()  # すべてのデータを取得
    test_add_data()      # 新しいデータを追加
    test_get_data_by_id(1)  # ID 1のデータを取得（追加後のIDを確認する必要あり）
    test_update_data(1)  # ID 1のデータを更新（追加後のIDを確認する必要あり）
    test_delete_data(1)  # ID 1のデータを削除（追加後のIDを確認する必要あり）
