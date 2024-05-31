import os
import platform
import json
from flask import Flask, render_template, redirect

app = Flask(__name__)

def custom_urlencode_filter(value):
    try:
        return round(value[0] / value[1] * 100)
    except Exception:
        return 0

def custom_divide(value, dec=0):
    try:
        return round(value[0] / value[1], dec)
    except Exception:
        return 0

def human_format(num):
    num = float('{:.3g}'.format(num))
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    return '{}{}'.format('{:f}'.format(num).rstrip('0').rstrip('.'), ['', 'K', 'M', 'B', 'T'][magnitude])

if platform.system() == "Linux":
    shared_folder = "/shared2/"
else:
    shared_folder = "D:/Projekte/Python/Drachbot/shared2/"

elos = [1800, 2000, 2200, 2400, 2600, 2800]
elos.reverse()
patches = ["11.04", "11.03", "11.02", "11.01", "11.00"]

@app.route("/")
def landing():
    return redirect("/mmstats")

@app.route('/mmstats/', defaults={"elo": 2200, "patch": "11.04"})
@app.route('/mmstats/<patch>/<elo>')
def mmstats(elo, patch):
    mmstats_data = None
    for file in os.listdir(shared_folder+f"data/mmstats/"):
        if file.startswith(f"{patch}_{elo}"):
            games = file.split("_")[2]
            if games == "o":
                return render_template("no_data.html")
            else:
                games = int(games)
            avg_elo = file.split("_")[3].replace(".json", "")
            with open(shared_folder+f"data/mmstats/"+file, "r") as f:
                mmstats_data = json.load(f)
                f.close()
    if not mmstats_data:
        return render_template("no_data.html")
    return render_template("mmstats.html", data=mmstats_data, elo_brackets=elos, custom_urlencode_filter=custom_urlencode_filter,
                           games=games, avg_elo = avg_elo, patch = patch, patch_list=patches, elo = elo, custom_divide = custom_divide, human_format= human_format)

if platform.system() == "Windows":
    app.run(debug=True)
else:
    from waitress import serve
    serve(app, host="0.0.0.0", port=54937)