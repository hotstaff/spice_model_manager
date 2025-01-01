from flask import Flask, render_template
from bokeh.plotting import figure, output_file, save
from bokeh.embed import components
import numpy as np

app = Flask(__name__)

@app.route('/')
def index():
    # Bokehのプロット作成
    x = np.linspace(0, 10, 100)
    y = np.sin(x)
    
    plot = figure(title="FlaskとBokehの統合", x_axis_label="X", y_axis_label="Y")
    plot.line(x, y, line_width=2)
    
    # BokehのプロットをHTMLに埋め込むためのコンポーネントを取得
    script, div = components(plot)
    
    # Flaskテンプレートに渡す
    return render_template("index.html", script=script, div=div)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
