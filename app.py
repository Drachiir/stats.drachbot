import os
import platform
import json
from datetime import datetime, timezone
from flask_caching import Cache
from flask import Flask, render_template, redirect, url_for, send_from_directory
import util

cache = Cache()

app = Flask(__name__)

if platform.system() == "Linux":
    timeout = 600
else:
    timeout = 1

app.config['CACHE_TYPE'] = 'simple' # Set the cache type
app.config['CACHE_DEFAULT_TIMEOUT'] = timeout # Set the default cache timeout in seconds
app.config['CACHE_KEY_PREFIX'] = 'myapp_' # Set the cache key prefix

cache.init_app(app)

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/robots.txt')
def robots():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'robots.txt', mimetype='text/plain')

@app.route('/sitemap.xml')
def sitemap():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'sitemap.xml')

if platform.system() == "Linux":
    shared_folder = "/shared2/"
else:
    shared_folder = "D:/Projekte/Python/Drachbot/shared2/"

with open("defaults.json", "r") as f:
    defaults_json = json.load(f)
    f.close()

defaults = defaults_json["Defaults"]
mm_list = defaults_json["MMs"]
elos = defaults_json["Elos"]
patches = defaults_json["Patches"]
buff_spells = defaults_json["BuffSpells"]

@app.route("/")
@cache.cached(timeout=timeout)
def home():
    folder_list = ["mmstats", "openstats", "spellstats", "unitstats"]
    header_list = ["MM", "Open", "Spell", "Unit"]
    title_list = ["MM Stats", "Opener Stats", "Spell Stats", "Unit Stats"]
    image_list =["https://cdn.legiontd2.com/icons/Mastermind.png", "https://cdn.legiontd2.com/icons/Mastery/5.png"
                 ,"https://cdn.legiontd2.com/icons/LegionSpell.png", "https://cdn.legiontd2.com/icons/Value10000.png"]
    data_list = []
    keys = []
    for i, folder in enumerate(folder_list):
        for file in os.listdir(shared_folder+f"data/{folder}/"):
            if file.startswith(f"{defaults[0]}_{defaults[1]}"):
                games = file.split("_")[2]
                games = int(games)
                avg_elo = file.split("_")[3].replace(".json", "")
                with open(shared_folder+f"data/{folder}/"+file, "r") as f:
                    json_data = json.load(f)
                    new_dict = {}
                    for key in json_data:
                        if json_data[key]["Count"] != 0:
                            new_dict[key] = json_data[key]
                    json_data = new_dict
                    temp_keys = list(json_data.keys())
                    keys.append([folder, temp_keys])
                    data_list.append([folder, games, avg_elo, json_data, header_list[i], title_list[i], temp_keys[:2]])
                    f.close()
                break
    total_games = "0"
    for file in os.listdir(shared_folder+f"data/mmstats"):
        temp_string = file.split("_")
        if temp_string[0] == defaults[0] and temp_string[1] == "1800":
            total_games = util.human_format(int(temp_string[2]))
            break
    return render_template("home.html", data_list=data_list, image_list=image_list, keys=keys,
                           elo=defaults[1], patch=defaults[0], get_cdn_image = util.get_cdn_image, get_key_value=util.get_key_value,
                           total_games=total_games)

@app.route('/<stats>/', defaults={"elo": defaults[1], "patch": defaults[0], "specific_key": "All"})
@app.route('/<stats>/<patch>/<elo>/', defaults={"specific_key": "All"})
@app.route('/<stats>/<patch>/<elo>/<specific_key>')
@cache.cached(timeout=timeout)
def stats(stats, elo, patch, specific_key):
    if stats not in ["mmstats", "openstats", "spellstats", "unitstats", "megamindstats"]:
        return render_template("no_data.html")
    raw_data = None
    match stats:
        case "megamindstats":
            header_title = "MM"
            header_cdn = "https://cdn.legiontd2.com/icons/Items/"
            title = "Megamind"
            title_image = "https://cdn.legiontd2.com/icons/Items/Megamind.png"
            folder = "megamindstats"
            if specific_key == "All" or specific_key == "Megamind":
                header_keys = ["Games", "Winrate", "Pickrate", "Player Elo", "W on 10"]
                sub_headers = [["Best Opener", "Opener", "openstats"], ["Best Spell", "Spell", "spellstats"]]
            else:
                header_keys = ["Games", "Winrate", "Playrate"]
                sub_headers = [["Openers", "Opener", "openstats"], ["Spells", "Spell", "spellstats"]]
            if specific_key != "All" and specific_key != "Megamind" and specific_key not in mm_list:
                return render_template("no_data.html")
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
                title_image = "https://cdn.legiontd2.com/icons/Items/Megamind.png"
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
                mod_date = util.time_ago(datetime.fromtimestamp(os.path.getmtime(shared_folder+f"data/{folder}/"+file)).timestamp())
                raw_data = json.load(f)
                f.close()
    if raw_data:
        if stats != "mmstats":
            new_dict = {}
            for key in raw_data:
                if raw_data[key]["Count"] != 0:
                    new_dict[key] = raw_data[key]
            raw_data = new_dict
    if not raw_data or ((stats != "mmstats" and stats != "megamindstats") and specific_key != "All" and specific_key not in raw_data):
        return render_template("no_data.html")
    if stats == "mmstats" and specific_key != "Megamind":
        if specific_key != "All" and raw_data[specific_key]["Count"] == 0:
            return render_template("no_data.html")
    if specific_key == "All" or (specific_key == "Megamind" and (stats == "mmstats" or stats == "megamindstats")):
        html_file = "stats.html"
    else:
        html_file = "stats_specific.html"
    return render_template(html_file, data=raw_data, elo_brackets=elos, custom_winrate=util.custom_winrate,
                           games=games, avg_elo = avg_elo, patch = patch, patch_list=patches, elo = elo, custom_divide = util.custom_divide,
                           human_format= util.human_format, get_perf_list=util.get_perf_list, get_dict_value=util.get_dict_value,
                           specific_key=specific_key, get_unit_name=util.get_unit_name, sort_dict=util.sort_dict, title=title, title_image=title_image,
                           stats=stats, header_cdn=header_cdn, header_title=header_title, header_keys=header_keys, get_key_value=util.get_key_value,
                           sub_headers=sub_headers, get_cdn_image=util.get_cdn_image, mm_list=mm_list, mod_date=mod_date, get_tooltip=util.get_tooltip,
                           data_keys = raw_data.keys(), get_rank_url=util.get_rank_url)

if platform.system() == "Windows":
    app.run(debug=True)
else:
    from waitress import serve
    serve(app, host="0.0.0.0", port=54937)