import os
import platform
import json
from datetime import datetime, timezone

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

@app.route('/<stats>/', defaults={"elo": defaults[1], "patch": defaults[0], "specific_key": "All"})
@app.route('/<stats>/<patch>/<elo>/', defaults={"specific_key": "All"})
@app.route('/<stats>/<patch>/<elo>/<specific_key>')
def stats(stats, elo, patch, specific_key):
    raw_data = None
    match stats:
        case "mmstats":
            title = "Mastermind"
            title_image = "https://cdn.legiontd2.com/icons/Mastermind.png"
            header_title = "MM"
            header_cdn = "https://cdn.legiontd2.com/icons/Items/"
            if specific_key == "All" or specific_key == "Megamind":
                header_keys = ["Games", "Winrate", "Pickrate", "Player Elo", "W on 10"]
                sub_headers = [["Best Opener", "Opener", "openstats"], ["Best Spell", "Spell", "spellstats"]]
            else:
                header_keys = ["Games", "Winrate", "Playrate"]
                sub_headers = [["Openers", "Opener", "openstats"], ["Spells", "Spell", "spellstats"]]
            if specific_key == "Megamind":
                title = "Megamind"
                folder = "megamindstats"
            else:
                folder = "mmstats"
            if specific_key != "All" and specific_key != "Megamind" and specific_key not in mm_list:
                return render_template("no_data.html")
        case "openstats":
            title = "Opener"
            title_image = "https://cdn.legiontd2.com/icons/Mastery/5.png"
            header_title = "Opener"
            header_cdn = "https://cdn.legiontd2.com/icons/"
            if specific_key == "All":
                header_keys = ["Games", "Winrate", "Pickrate", "Player Elo", "W on 4"]
                sub_headers = [["Best Add", "OpenWith", "unitstats"], ["Best MMs", "MMs", "mmstats"], ["Best Spell", "Spells", "spellstats"]]
            else:
                header_keys = ["Games", "Winrate", "Playrate"]
                sub_headers = [["Adds", "OpenWith", "unitstats"], ["MMs", "MMs", "mmstats"], ["Spells", "Spells", "spellstats"]]
            folder = "openstats"
        case "spellstats":
            title = "Spell"
            title_image = "https://cdn.legiontd2.com/icons/LegionSpell.png"
            header_title = "Spell"
            header_cdn = "https://cdn.legiontd2.com/icons/"
            if specific_key == "All":
                header_keys = ["Games", "Winrate", "Pickrate", "Player Elo", "W on 10"]
                sub_headers = [["Best Opener", "Opener", "openstats"], ["Best MMs", "MMs", "mmstats"]]
            else:
                if specific_key in buff_spells:
                    header_keys = ["Games", "Winrate", "Playrate"]
                    sub_headers = [["Targets", "Targets", "unitstats"], ["Openers", "Opener", "openstats"], ["MMs", "MMs", "mmstats"]]
                else:
                    header_keys = ["Games", "Winrate", "Playrate"]
                    sub_headers = [["Openers", "Opener", "openstats"], ["MMs", "MMs", "mmstats"]]
            folder = "spellstats"
        case "unitstats":
            title = "Unit"
            title_image = "https://cdn.legiontd2.com/icons/Value10000.png"
            header_title = "Unit"
            header_cdn = "https://cdn.legiontd2.com/icons/"
            if specific_key == "All":
                header_keys = ["Games", "Winrate", "Pickrate", "Player Elo"]
                sub_headers = [["Best Combo", "ComboUnit", "unitstats"], ["Best MMs", "MMs", "mmstats"], ["Best Spell", "Spells", "spellstats"]]
            else:
                header_keys = ["Games", "Winrate", "Playrate"]
                sub_headers = [["Combos", "ComboUnit", "unitstats"], ["MMs", "MMs", "mmstats"], ["Spells", "Spells", "spellstats"]]
            folder = "unitstats"
    for file in os.listdir(shared_folder+f"data/{folder}/"):
        if file.startswith(f"{patch}_{elo}"):
            games = file.split("_")[2]
            if games == "o":
                return render_template("no_data.html")
            else:
                games = int(games)
            avg_elo = file.split("_")[3].replace(".json", "")
            with open(shared_folder+f"data/{folder}/"+file, "r") as f:
                mod_date = util.time_ago(datetime.fromtimestamp(os.path.getmtime(shared_folder+f"data/{folder}/"+file), tz=timezone.utc).timestamp())
                raw_data = json.load(f)
                f.close()
    new_dict = {}
    for key in raw_data:
        if raw_data[key]["Count"] != 0:
            new_dict[key] = raw_data[key]
    raw_data = new_dict
    if not raw_data or (stats != "mmstats" and specific_key != "All" and specific_key not in raw_data):
        return render_template("no_data.html")
    if specific_key == "All" or (specific_key == "Megamind" and stats == "mmstats"):
        html_file = "stats.html"
    else:
        html_file = "stats_specific.html"
    return render_template(html_file, data=raw_data, elo_brackets=elos, custom_winrate=util.custom_winrate,
                           games=games, avg_elo = avg_elo, patch = patch, patch_list=patches, elo = elo, custom_divide = util.custom_divide,
                           human_format= util.human_format, get_perf_list=util.get_perf_list, get_dict_value=util.get_dict_value,
                           specific_key=specific_key, get_unit_name=util.get_unit_name, sort_dict=util.sort_dict, title=title, title_image=title_image,
                           stats=stats, header_cdn=header_cdn, header_title=header_title, header_keys=header_keys, get_key_value=util.get_key_value,
                           sub_headers=sub_headers, get_cdn_image=util.get_cdn_image, mm_list=mm_list, mod_date=mod_date)

if platform.system() == "Windows":
    app.run(debug=True)
else:
    from waitress import serve
    serve(app, host="0.0.0.0", port=54937)