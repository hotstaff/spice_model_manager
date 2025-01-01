from flask import Flask, render_template
from bokeh.plotting import figure
from bokeh.embed import components

app = Flask(__name__)

@app.route('/')
def index():
    # Bokehプロットを作成
    plot = figure(title="FlaskとBokehの統合", x_axis_label='X', y_axis_label='Y')
    plot.line([1, 2, 3, 4, 5], [6, 7, 2, 4, 5], legend_label="Line", line_width=2)

    # Bokehのコンポーネントを取得
    script, div = components(plot)

    # HTMLに埋め込む
    return render_template('index.html', script=script, div=div)

if __name__ == '__main__':
    app.run(debug=True)
