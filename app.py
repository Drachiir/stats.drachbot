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

defaults = ["11.04", 2200]
mm_list = ['All', 'LockIn', 'Greed', 'Redraw', 'Yolo', 'Fiesta', 'CashOut', 'Castle', 'Cartel', 'Chaos', 'Champion', 'DoubleLockIn', 'Kingsguard']
elos = [1800, 2000, 2200, 2400, 2600, 2800]
elos.reverse()
patches = ["11.04", "11.03", "11.02", "11.01", "11.00"]
buff_spells = ["hero", "magician", "vampire", "divine blessing", "glacial touch", "guardian angel", "protector", "pulverizer", "sorcerer", "titan", "villain"]

@app.route("/")
def landing():
    return redirect("/mmstats")

@app.route('/mmstats/', defaults={"elo": defaults[1], "patch": defaults[0], "mm": "All"})
@app.route('/mmstats/<patch>/<elo>/', defaults={"mm": "All"})
@app.route('/mmstats/<patch>/<elo>/<mm>')
def mmstats(elo, patch, mm):
    mmstats_data = None
    if mm == "Megamind":
        folder = "megamindstats"
    else:
        folder = "mmstats"
    for file in os.listdir(shared_folder+f"data/{folder}/"):
        if file.startswith(f"{patch}_{elo}"):
            games = file.split("_")[2]
            if games == "o":
                return render_template("no_data.html")
            else:
                games = int(games)
            avg_elo = file.split("_")[3].replace(".json", "")
            with open(shared_folder+f"data/{folder}/"+file, "r") as f:
                mmstats_data = json.load(f)
                f.close()
    if not mmstats_data:
        return render_template("no_data.html")
    if mm != "All" and mm != "Megamind" and mm not in mm_list:
        return render_template("no_data.html")
    if mm == "All":
        html_file = "mmstats.html"
    elif mm != "Megamind":
        html_file = "mmstats_specific.html"
    else:
        html_file = "megamindstats.html"
    return render_template(html_file, data=mmstats_data, elo_brackets=elos, custom_winrate=util.custom_winrate,
                           games=games, avg_elo = avg_elo, patch = patch, patch_list=patches, elo = elo, custom_divide = util.custom_divide,
                           human_format= util.human_format, get_perf_list=util.get_perf_list, get_dict_value=util.get_dict_value,
                           specific_mm=mm, mm_list = mm_list, get_unit_name=util.get_unit_name, sort_dict=util.sort_dict)

@app.route('/openstats/', defaults={"elo": defaults[1], "patch": defaults[0], "opener": "All"})
@app.route('/openstats/<patch>/<elo>/', defaults={"opener": "All"})
@app.route('/openstats/<patch>/<elo>/<opener>')
def openstats(elo, patch, opener):
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
    if opener != "All" and opener not in new_dict:
        return render_template("no_data.html")
    if opener == "All":
        html_file = "openstats.html"
    else:
        html_file = "openstats_specific.html"
    return render_template(html_file, data=new_dict, elo_brackets=elos, custom_winrate=util.custom_winrate,
                           games=games, avg_elo = avg_elo, patch = patch, patch_list=patches, elo = elo, custom_divide = util.custom_divide,
                           human_format= util.human_format, get_perf_list=util.get_perf_list, get_dict_value=util.get_dict_value,
                           get_unit_name=util.get_unit_name, get_unit_name_list=util.get_unit_name_list, specific_open=opener, unit_list = new_dict.keys(),
                           sort_dict=util.sort_dict)

@app.route('/unitstats/', defaults={"elo": defaults[1], "patch": defaults[0], "unit": "All"})
@app.route('/unitstats/<patch>/<elo>/', defaults={"unit": "All"})
@app.route('/unitstats/<patch>/<elo>/<unit>')
def unitstats(elo, patch, unit):
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
    if unit != "All" and unit not in new_dict:
        return render_template("no_data.html")
    if unit == "All":
        html_file = "unitstats.html"
    else:
        html_file = "unitstats_specific.html"
    return render_template(html_file, data=new_dict, elo_brackets=elos, custom_winrate=util.custom_winrate,
                           games=games, avg_elo = avg_elo, patch = patch, patch_list=patches, elo = elo, custom_divide = util.custom_divide,
                           human_format= util.human_format, get_perf_list=util.get_perf_list, get_dict_value=util.get_dict_value,
                           get_unit_name=util.get_unit_name, get_unit_name_list=util.get_unit_name_list, specific_unit = unit, sort_dict=util.sort_dict)

@app.route('/spellstats/', defaults={"elo": defaults[1], "patch": defaults[0], "spell": "All"})
@app.route('/spellstats/<patch>/<elo>/', defaults={"spell": "All"})
@app.route('/spellstats/<patch>/<elo>/<spell>')
def spellstats(elo, patch, spell):
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
    if spell != "All" and spell not in new_dict:
        return render_template("no_data.html")
    if spell == "All":
        html_file = "spellstats.html"
    else:
        html_file = "spellstats_specific.html"
    return render_template(html_file, data=new_dict, elo_brackets=elos, custom_winrate=util.custom_winrate,
                           games=games, avg_elo = avg_elo, patch = patch, patch_list=patches, elo = elo, custom_divide = util.custom_divide,
                           human_format= util.human_format, get_perf_list=util.get_perf_list, get_dict_value=util.get_dict_value,
                           get_unit_name=util.get_unit_name, get_unit_name_list=util.get_unit_name_list, specific_spell = spell, sort_dict=util.sort_dict,
                           buff_spells = buff_spells)

if platform.system() == "Windows":
    app.run(debug=True)
else:
    from waitress import serve
    serve(app, host="0.0.0.0", port=54937)