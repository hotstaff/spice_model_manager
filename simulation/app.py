import os
from flask import Flask

app = Flask(__name__)

@app.route('/')
def hello_world():
    return 'Hello from your friendly neighborhood Flask app!'

if __name__ == '__main__':
    # PORT環境変数を取得し、デフォルト値は8080
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
