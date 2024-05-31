import os
import platform
import json
from flask import Flask, render_template, redirect
import util

app = Flask(__name__)

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
    return render_template("mmstats.html", data=mmstats_data, elo_brackets=elos, custom_winrate=util.custom_winrate,
                           games=games, avg_elo = avg_elo, patch = patch, patch_list=patches, elo = elo, custom_divide = util.custom_divide,
                           human_format= util.human_format, get_perf_list=util.get_perf_list, get_dict_value=util.get_dict_value)

@app.route('/openstats/', defaults={"elo": 2200, "patch": "11.04"})
@app.route('/openstats/<patch>/<elo>')
def openstats(elo, patch):
    openstats_data = None
    for file in os.listdir(shared_folder+f"data/openstats/"):
        if file.startswith(f"{patch}_{elo}"):
            games = file.split("_")[2]
            if games == "o":
                return render_template("no_data.html")
            else:
                games = int(games)
            avg_elo = file.split("_")[3].replace(".json", "")
            with open(shared_folder+f"data/openstats/"+file, "r") as f:
                openstats_data = json.load(f)
                f.close()
    if not openstats_data:
        return render_template("no_data.html")
    new_dict = {}
    for key in openstats_data:
        if openstats_data[key]["Count"] != 0:
            new_dict[key] = openstats_data[key]
    return render_template("openstats.html", data=new_dict, elo_brackets=elos, custom_winrate=util.custom_winrate,
                           games=games, avg_elo = avg_elo, patch = patch, patch_list=patches, elo = elo, custom_divide = util.custom_divide,
                           human_format= util.human_format, get_perf_list=util.get_perf_list, get_dict_value=util.get_dict_value,
                           get_unit_name=util.get_unit_name, get_unit_name_list=util.get_unit_name_list)

@app.route('/unitstats/', defaults={"elo": 2200, "patch": "11.04"})
@app.route('/unitstats/<patch>/<elo>')
def unitstats(elo, patch):
    unitstats_data = None
    for file in os.listdir(shared_folder+f"data/unitstats/"):
        if file.startswith(f"{patch}_{elo}"):
            games = file.split("_")[2]
            if games == "o":
                return render_template("no_data.html")
            else:
                games = int(games)
            avg_elo = file.split("_")[3].replace(".json", "")
            with open(shared_folder+f"data/unitstats/"+file, "r") as f:
                unitstats_data = json.load(f)
                f.close()
    if not unitstats_data:
        return render_template("no_data.html")
    new_dict = {}
    for key in unitstats_data:
        if unitstats_data[key]["Count"] != 0:
            new_dict[key] = unitstats_data[key]
    return render_template("unitstats.html", data=new_dict, elo_brackets=elos, custom_winrate=util.custom_winrate,
                           games=games, avg_elo = avg_elo, patch = patch, patch_list=patches, elo = elo, custom_divide = util.custom_divide,
                           human_format= util.human_format, get_perf_list=util.get_perf_list, get_dict_value=util.get_dict_value,
                           get_unit_name=util.get_unit_name, get_unit_name_list=util.get_unit_name_list)

@app.route('/spellstats/', defaults={"elo": 2200, "patch": "11.04"})
@app.route('/spellstats/<patch>/<elo>')
def spellstats(elo, patch):
    spellstats_data = None
    for file in os.listdir(shared_folder+f"data/spellstats/"):
        if file.startswith(f"{patch}_{elo}"):
            games = file.split("_")[2]
            if games == "o":
                return render_template("no_data.html")
            else:
                games = int(games)
            avg_elo = file.split("_")[3].replace(".json", "")
            with open(shared_folder+f"data/spellstats/"+file, "r") as f:
                spellstats_data = json.load(f)
                f.close()
    if not spellstats_data:
        return render_template("no_data.html")
    new_dict = {}
    for key in spellstats_data:
        if spellstats_data[key]["Count"] != 0:
            new_dict[key] = spellstats_data[key]
    return render_template("spellstats.html", data=new_dict, elo_brackets=elos, custom_winrate=util.custom_winrate,
                           games=games, avg_elo = avg_elo, patch = patch, patch_list=patches, elo = elo, custom_divide = util.custom_divide,
                           human_format= util.human_format, get_perf_list=util.get_perf_list, get_dict_value=util.get_dict_value,
                           get_unit_name=util.get_unit_name, get_unit_name_list=util.get_unit_name_list)

if platform.system() == "Windows":
    app.run(debug=True)
else:
    from waitress import serve
    serve(app, host="0.0.0.0", port=54937)