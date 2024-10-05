import os
import platform
import json
from datetime import datetime, timezone, timedelta
from flask_caching import Cache
from flask import Flask, render_template, redirect, url_for, send_from_directory, request, session
import re
import drachbot.legion_api as legion_api
import drachbot.drachbot_db as drachbot_db
import drachbot.mmstats
import drachbot.openstats
import drachbot.spellstats
import drachbot.unitstats
import drachbot.wavestats
import util
from drachbot.peewee_pg import GameData, PlayerData
from util import get_rank_url, custom_winrate, plus_prefix, custom_divide
from flask_apscheduler import APScheduler
from playfab import PlayFabClientAPI, PlayFabSettings

cache = Cache()

app = Flask(__name__)
app.secret_key = 'python>js'
scheduler = APScheduler()

def leaderboard_task():
    PlayFabSettings.TitleId = "9092"
    
    login_request = {
        "TitleId": "9092",
        "CustomId": "LTD2Website",
        "CreateAccount": False
    }
    
    leaderboard_request = {
        "TitleId": "9092",
        "CustomId": "LTD2Website",
        "CreateAccount": False,
        "StartPosition": 0,
        "StatisticName": "overallEloThisSeasonAtLeastOneGamePlayed",
        "MaxResultsCount": 100,
        "ProfileConstraints": {
            "ShowDisplayName": True,
            "ShowStatistics": True,
            "ShowLocations": True,
            "ShowAvatarUrl": True,
            "ShowContactEmailAddresses": True
        }
    }
    
    def callback(success, failure):
        if success:
            if len(success) < 1:
                print("leaderboard fetch error")
                return
            with open("leaderboard.json", "w") as f:
                json.dump(success, f)
        else:
            if failure:
                print(failure.GenerateErrorReport())
    PlayFabClientAPI.LoginWithCustomID(login_request, callback)
    PlayFabClientAPI.GetLeaderboard(leaderboard_request, callback)

if platform.system() == "Linux":
    timeout = 600
    timeout2 = 300
else:
    timeout = 1
    timeout2 = 1
    
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
    shared_folder_live = "/shared/livegames"
    shared_folder = "/shared2/"
else:
    shared_folder = "D:/Projekte/Python/Drachbot/shared2/"
    shared_folder_live = "shared/livegames"

with open("defaults.json", "r") as f:
    defaults_json = json.load(f)
    f.close()

defaults = defaults_json["Defaults"]
defaults2 = defaults_json["Defaults2"]
mm_list = defaults_json["MMs"]
elos = defaults_json["Elos"]
patches = defaults_json["Patches"]
patches2 = defaults_json["Patches2"]
buff_spells = defaults_json["BuffSpells"]

@app.route("/")
@cache.cached(timeout=timeout)
def home():
    folder_list = ["mmstats", "openstats", "spellstats", "rollstats", "megamindstats", "unitstats", "wavestats"]
    header_list = ["MM", "Open", "Spell", "Roll", "MM", "Unit", "Wave"]
    title_list = ["MM Stats", "Opener Stats", "Spell Stats", "Roll Stats", "MM Stats", "Unit Stats", "Wave Stats"]
    image_list =["https://cdn.legiontd2.com/icons/Mastermind.png", "https://cdn.legiontd2.com/icons/Mastery/5.png"
                 ,"https://cdn.legiontd2.com/icons/LegionSpell.png", "https://cdn.legiontd2.com/icons/Reroll.png", "https://cdn.legiontd2.com/icons/Items/Megamind.png"
                 ,"https://cdn.legiontd2.com/icons/Value10000.png","https://cdn.legiontd2.com/icons/LegionKing.png"]
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
                    if folder == "wavestats":
                        newIndex = sorted(json_data, key=lambda x: json_data[x]['EndCount'], reverse=True)
                        json_data = {k: json_data[k] for k in newIndex}
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
                           total_games=total_games, get_tooltip = util.get_tooltip, home=True)

@app.route('/classicmodes')
@cache.cached(timeout=60)
def classic_modes():
    increment_in_seconds = 5.75 * 60 * 60
    start_utc = datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    now = datetime.now(tz=timezone.utc)
    
    seconds_elapsed = (now - start_utc).total_seconds()
    
    increments_since_start = int(seconds_elapsed // increment_in_seconds)
    
    current_increment_start = start_utc + timedelta(seconds=increments_since_start * increment_in_seconds)
    
    increment_delta = timedelta(seconds=increment_in_seconds)
    schedule = [
        {
            'mode': util.modes[(increments_since_start + i) % len(util.modes)],
            'start': (current_increment_start + i * increment_delta).isoformat(),
            'end': (current_increment_start + (i + 1) * increment_delta).isoformat(),
            'cdn_link': f"https://cdn.legiontd2.com/icons/ClassicModes/{util.images[util.modes[(increments_since_start + i) % len(util.modes)]]}.png"
        }
        for i in range(16)
    ]
    return render_template('classic_modes.html', schedule=schedule, classic_schedule = True)

@app.route("/leaderboard")
@cache.cached(timeout=timeout2)
def leaderboard():
    with open("leaderboard.json", "r") as f:
        leaderboard_data = json.load(f)
    return render_template("leaderboard.html", leaderboard = leaderboard_data, get_rank_url=util.get_rank_url, get_value=util.get_value_playfab,
                           winrate = util.custom_winrate)

@app.route("/api/livegames")
def livegames_api():
    games = []
    for game in os.listdir(shared_folder_live):
        try:
            with open(f"{shared_folder_live}/{game}", "r", encoding="utf_8") as f2:
                txt = f2.readlines()
                f2.close()
        except FileNotFoundError:
            continue
        path2 = f"{shared_folder_live}/{game}"
        mod_date = datetime.fromtimestamp(os.path.getmtime(path2), tz=timezone.utc).timestamp()
        game_elo = txt[-1]
        west_players = [txt[0].replace("\n", "").split(":"), txt[1].replace("\n", "").split(":")]
        east_players = [txt[2].replace("\n", "").split(":"), txt[3].replace("\n", "").split(":")]
        games.append([mod_date, game_elo, west_players, east_players])
    games = sorted(games, key=lambda x: int(x[1]), reverse=True)[:21]
    return games

@app.route("/gameviewer/<gameid>", defaults={"wave": 1})
@app.route("/gameviewer/<gameid>/<wave>")
def gameviewer(gameid, wave):
    data = drachbot.drachbot_db.get_game_by_id(gameid)
    if data == {"Error": "Game not found."}:
        return render_template("no_data.html", text="Game ID not found/valid")
    return render_template("gameviewer.html", game_data = data, game_viewer = True, get_cdn=util.get_cdn_image, get_rank_url=util.get_rank_url,
                           const_file = util.const_file, plus_prefix = util.plus_prefix, wave=wave)
    
@app.route("/livegames")
def livegames():
    return render_template("livegames.html", get_rank_url=get_rank_url, livegames = True)

@app.route('/load/<playername>/', defaults={"stats": None,"elo": defaults[1], "patch": defaults[0], "specific_key": "All"})
@app.route('/load/<playername>/<stats>/', defaults={"elo": defaults[1], "patch": defaults[0], "specific_key": "All"})
@app.route('/load/<playername>/<stats>/<patch>/', defaults={"elo": defaults[1], "specific_key": "All"})
@app.route('/load/<playername>/<stats>/<patch>/<elo>/', defaults={"specific_key": "All"})
@app.route('/load/<playername>/<stats>/<patch>/<elo>/<specific_key>/')
def load(playername, stats, patch, elo, specific_key):
    session['visited_profile'] = True
    if not stats:
        new_patch = request.args.get('patch')
        if new_patch:
            new_patch = f"?patch={new_patch}"
        else:
            new_patch = ""
        return render_template('loading.html', playername=playername, url=f"/profile/{playername}/{new_patch}")
    else:
        return render_template('loading.html', playername=playername, url=f"/profile/{playername}/{stats}/{patch}/{elo}/{specific_key}/")

@app.route('/profile/<playername>/', defaults={"stats": None,"elo": defaults2[1], "patch": defaults2[0], "specific_key": "All"})
@app.route('/profile/<playername>/<stats>/', defaults={"elo": defaults2[1], "patch": defaults2[0], "specific_key": "All"})
@app.route('/profile/<playername>/<stats>/<patch>/', defaults={"elo": defaults2[1], "specific_key": "All"})
@app.route('/profile/<playername>/<stats>/<patch>/<elo>/', defaults={"specific_key": "All"})
@app.route('/profile/<playername>/<stats>/<patch>/<elo>/<specific_key>/')
def profile(playername, stats, patch, elo, specific_key):
    if not stats:
        new_patch = request.args.get('patch')
        if new_patch:
            patch = new_patch.replace("/", "")
            if "11" in patch.split(","):
                patch = "11"
                new_patch = "11"
            new_patch = f"?patch={new_patch}"
        else:
            new_patch = ""
        if not session.get('visited_profile'):
            return redirect(f"/load/{playername}/{new_patch}")
        session.pop('visited_profile', None)
        referrer = request.referrer
        if not referrer or '/load' not in referrer:
            return redirect(f"/load/{playername}/{new_patch}")
        if len(playername) == 16 and re.fullmatch(r'[0-9A-F]+', playername):
            playerid = playername
            api_profile = legion_api.getprofile(playername, by_id=True)
        else:
            api_profile = legion_api.getprofile(playername)
            if api_profile in [0, 1]:
                return render_template("no_data.html", text=f"{playername} not found.")
            playerid = api_profile["_id"]
        api_stats = legion_api.getstats(playerid)
        try:
            _ = api_stats["rankedWinsThisSeason"]
            _ = api_stats["rankedLossesThisSeason"]
            _ = api_stats["overallElo"]
            _ = api_stats["overallPeakEloThisSeason"]
        except KeyError:
            return render_template("no_data.html", text=f"{playername} not found.")
        stats_list = ["mmstats", "megamindstats", "openstats", "spellstats", "rollstats", "unitstats", "wavestats"]
        image_list = [
            "https://cdn.legiontd2.com/icons/Mastermind.png",
            "https://cdn.legiontd2.com/icons/Items/Megamind.png",
            "https://cdn.legiontd2.com/icons/Mastery/5.png",
            "https://cdn.legiontd2.com/icons/LegionSpell.png",
            "https://cdn.legiontd2.com/icons/Reroll.png",
            "https://cdn.legiontd2.com/icons/Value10000.png",
            "https://cdn.legiontd2.com/icons/LegionKing.png"
        ]
        path = f"Files/player_cache/{api_profile["playerName"]}_profile_{patch}.json"
        history = None
        if os.path.isfile(path):
            mod_date = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)
            date_diff = datetime.now(tz=timezone.utc) - mod_date
            minutes_diff = date_diff.total_seconds() / 60
            if minutes_diff > 5:
                os.remove(path)
            else:
                with open(path, "r") as f:
                    history = json.load(f)
        if not history:
            req_columns = [
                [GameData.game_id, GameData.queue, GameData.date, GameData.version, GameData.ending_wave, GameData.game_elo, GameData.player_ids, GameData.game_length,
                 PlayerData.player_id, PlayerData.player_name, PlayerData.player_elo, PlayerData.player_slot, PlayerData.game_result, PlayerData.elo_change,
                 PlayerData.legion, PlayerData.mercs_sent_per_wave, PlayerData.kingups_sent_per_wave, PlayerData.opener, PlayerData.megamind, PlayerData.spell, PlayerData.workers_per_wave],
                ["game_id", "date", "version", "ending_wave", "game_elo", "game_length"],
                ["player_id", "player_name", "player_elo", "player_slot", "game_result", "elo_change", "legion",
                 "mercs_sent_per_wave", "kingups_sent_per_wave", "opener", "megamind", "spell", "workers_per_wave"]]
            history = drachbot_db.get_matchistory(playerid, 0, elo, patch, earlier_than_wave10=True, req_columns=req_columns, stats=api_stats, profile=api_profile, pname=playername)
            with open(path, "w") as f:
                json.dump(history, f, default=str)
        history_parsed = []
        winlose = [0, 0]
        elochange = 0
        values = []
        labels = []
        mms = {}
        wave1 = {"King": 0, "Snail": 0, "Save": 0}
        openers = {}
        spells = {}
        player_map = {1: [1,2,3], 2: [0,2,3], 5: [3,0,1], 6: [2,0,1]}
        player_dict = {"Teammates": {}, "Enemies": {}}
        games = len(history)
        short_history = 20
        for game in history:
            if type(game["date"]) == str:
                game["date"] = datetime.strptime(game["date"].split(" ")[0], "%Y-%m-%d")
            end_wave_cdn = util.get_cdn_image(str(game["ending_wave"]), "Wave")
            temp_dict = {"EndWave": end_wave_cdn, "Result_String": "", "Version": game["version"], "EloChange": ""
                         ,"Date": game["date"], "gamelink": f"/gameviewer/{game["game_id"]}",
                         "time_ago": util.time_ago(game["date"]), "players_data": [], "Opener": "", "Mastermind": "", "Spell": "", "Worker": "", "Megamind": False}
            for player in game["players_data"]:
                temp_dict["players_data"].append([player["player_name"], player["player_elo"]])
                if player["player_id"] == playerid:
                    # Players
                    teammate = game["players_data"][player_map[player["player_slot"]][0]]
                    enemy1 = game["players_data"][player_map[player["player_slot"]][1]]
                    enemy2 = game["players_data"][player_map[player["player_slot"]][2]]
                    for p in [[teammate, "Teammates"],[enemy1, "Enemies"],[enemy2, "Enemies"]]:
                        if p[0]["player_id"] in player_dict[p[1]]:
                            player_dict[p[1]][p[0]["player_id"]]["Count"] += 1
                            player_dict[p[1]][p[0]["player_id"]]["Playername"] = p[0]["player_name"]
                            player_dict[p[1]][p[0]["player_id"]]["EloChange"] += player["elo_change"]
                        else:
                            player_dict[p[1]][p[0]["player_id"]] = {"Count": 1, "Wins": 0, "Playername": p[0]["player_name"], "EloChange": player["elo_change"]}
                        if player["game_result"] == "won":
                            player_dict[p[1]][p[0]["player_id"]]["Wins"] += 1
                    #Match history details
                    temp_dict["Opener"] = player["opener"]
                    temp_dict["Mastermind"] = player["legion"]
                    try:
                        temp_dict["Spell"] = player["spell"]
                    except KeyError:
                        temp_dict["Spell"] = "None"
                    if player["megamind"]:
                        temp_dict["Megamind"] = True
                    temp_dict["Worker"] = round(player["workers_per_wave"][-1], 1)
                    #Fav MM
                    if player["megamind"]:
                        player["legion"] = "Megamind"
                    if player["legion"] in mms:
                        mms[player["legion"]] += 1
                    else:
                        mms[player["legion"]] = 1
                    #Wave 1 Tendency
                    if player["mercs_sent_per_wave"][0].split("!")[0] == "Snail":
                        wave1["Snail"] += 1
                    elif str(player["kingups_sent_per_wave"][0].split("!")[0]).startswith("Upgrade"):
                        wave1["King"] += 1
                    else:
                        wave1["Save"] += 1
                    #Fav Opener
                    for opener_unit in set(player["opener"].split(",")):
                        if opener_unit in openers:
                            openers[opener_unit] += 1
                        else:
                            openers[opener_unit] = 1
                    #Fav Spells
                    try:
                        if player["spell"] != "none":
                            if player["spell"] in spells:
                                spells[player["spell"]] += 1
                            else:
                                spells[player["spell"]] = 1
                    except KeyError:
                        pass
                    values.insert(0, player["player_elo"]+player["elo_change"])
                    game_date = game["date"]
                    labels.insert(0,game_date.strftime("%d/%m/%Y"))
                    temp_dict["EloChange"] = util.plus_prefix(player["elo_change"])
                    if player["game_result"] == "won":
                        won = True
                        elochange += player["elo_change"]
                        winlose[0] += 1
                    else:
                        won = False
                        elochange += player["elo_change"]
                        winlose[1] += 1
                    temp_dict["Result_String"] = [won, f"Wave {game["ending_wave"]}"]
            history_parsed.append(temp_dict)
        newIndex = sorted(mms, key=lambda x: mms[x], reverse=True)
        mms = {k: mms[k] for k in newIndex[:5]}
        newIndex = sorted(openers, key=lambda x: openers[x], reverse=True)
        openers = {k: openers[k] for k in newIndex[:5]}
        newIndex = sorted(spells, key=lambda x: spells[x], reverse=True)
        spells = {k: spells[k] for k in newIndex[:5]}
        newIndex = sorted(player_dict["Teammates"], key=lambda x: player_dict["Teammates"][x]["Count"], reverse=True)
        player_dict["Teammates"] = {k: player_dict["Teammates"][k] for k in newIndex}
        newIndex = sorted(player_dict["Enemies"], key=lambda x: player_dict["Enemies"][x]["Count"], reverse=True)
        player_dict["Enemies"] = {k: player_dict["Enemies"][k] for k in newIndex}
        wave1_percents = []
        for val in wave1:
            try:
                wave1_percents.append(round(wave1[val]/games*100))
            except Exception:
                wave1_percents.append(0)
        player_rank = ""
        with open("leaderboard.json", "r") as f:
            leaderboard_data = json.load(f)
            f.close()
        for i, player in enumerate(leaderboard_data["Leaderboard"]):
            if player["DisplayName"] == api_profile["playerName"]:
                player_rank = f"Rank #{i+1}"
                break
        return render_template(
            "profile.html",
            api_profile=api_profile, api_stats=api_stats, get_rank_url=util.get_rank_url, winrate=util.custom_winrate,
            stats_list=stats_list, image_list=image_list, playername=playername, history=history_parsed, short_history = short_history,
            winlose=winlose, elochange=util.plus_prefix(elochange), playerurl = f"/profile/{playername}/", values=values,
            labels=labels, games=games, wave1 = wave1_percents, mms = mms, openers = openers, get_cdn = util.get_cdn_image, elo=elo,
            patch = patch, spells = spells, player_dict=player_dict, profile=True, plus_prefix=util.plus_prefix, patch_list = patches2,
            player_rank=player_rank)
    else:
        patches = patches2
        try:
            elo = int(elo)
        except Exception:
            return render_template("no_data.html", text="No Data")
        if not session.get('visited_profile'):
            return redirect(f"/load/{playername}/{stats}/{patch}/{elo}/{specific_key}/")
        session.pop('visited_profile', None)
        referrer = request.referrer
        if not referrer or '/load' not in referrer:
            return redirect(f"/load/{playername}/{stats}/{patch}/{elo}/{specific_key}/")
        
        if stats not in ["mmstats", "openstats", "spellstats", "unitstats", "megamindstats", "rollstats", "wavestats"]:
            return render_template("no_data.html", text="No Data")
        raw_data = None
        api_profile = legion_api.getprofile(playername)
        playerid = api_profile["_id"]
        if playerid in [0, 1]:
            return render_template("no_data.html", text=f"{playername} not found.")
        playername2 = api_profile["playerName"]
        #GET GAMES JSON
        path = f"Files/player_cache/{playername2}_{patch}_{elo}.json"
        history_raw = None
        if os.path.isfile(path):
            mod_date = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)
            date_diff = datetime.now(tz=timezone.utc) - mod_date
            minutes_diff = date_diff.total_seconds() / 60
            if minutes_diff > 30:
                os.remove(path)
            else:
                with open(path, "r") as f:
                    history_raw = json.load(f)
        if not history_raw:
            req_columns = [[GameData.game_id, GameData.queue, GameData.date, GameData.version, GameData.ending_wave, GameData.game_elo, GameData.player_ids, GameData.spell_choices,
                            PlayerData.player_id, PlayerData.player_slot, PlayerData.game_result, PlayerData.player_elo, PlayerData.legion, PlayerData.opener, PlayerData.spell,
                            PlayerData.workers_per_wave, PlayerData.megamind, PlayerData.build_per_wave, PlayerData.champ_location, PlayerData.spell_location, PlayerData.fighters,
                            PlayerData.mercs_sent_per_wave, PlayerData.leaks_per_wave, PlayerData.kingups_sent_per_wave, PlayerData.fighter_value_per_wave],
                           ["game_id", "queue", "date", "version", "ending_wave", "game_elo", "spell_choices"],
                           ["player_id", "player_slot", "game_result", "player_elo", "legion", "opener", "spell", "workers_per_wave", "megamind", "build_per_wave",
                            "champ_location", "spell_location", "fighters", "mercs_sent_per_wave", "leaks_per_wave", "kingups_sent_per_wave", "fighter_value_per_wave"]]
            history_raw = drachbot_db.get_matchistory(playerid, 0, elo, patch, earlier_than_wave10=True, req_columns=req_columns, pname=playername)
            with open(path, "w") as f:
                json.dump(history_raw, f, default=str)
        match stats:
            case "megamindstats":
                header_title = "MM"
                header_cdn = "https://cdn.legiontd2.com/icons/Items/"
                title = f"{playername2}'s Megamind"
                title_image = "https://cdn.legiontd2.com/icons/Items/Megamind.png"
                raw_data = drachbot.mmstats.mmstats(playerid,0,elo,patch,"Megamind", data_only=True, history_raw=history_raw)
                games = raw_data[1]
                avg_elo = raw_data[2]
                raw_data= raw_data[0]
                if specific_key == "Megamind":
                    specific_key = "All"
                if specific_key == "All":
                    header_keys = ["Games", "Winrate", "Playrate", "Player Elo", "W on 10"]
                    sub_headers = [["Best Opener", "Opener", "openstats"], ["Best Spell", "Spell", "spellstats"], ["Best Roll", "Rolls", "rollstats"]]
                elif specific_key == "Champion":
                    header_keys = ["Games", "Winrate", "Playrate"]
                    sub_headers = [["Champions", "Targets", "unitstats"], ["Openers", "Opener", "openstats"], ["Spells", "Spell", "spellstats"], ["Rolls", "Rolls", "rollstats"]]
                else:
                    header_keys = ["Games", "Winrate", "Playrate"]
                    sub_headers = [["Openers", "Opener", "openstats"], ["Spells", "Spell", "spellstats"], ["Rolls", "Rolls", "rollstats"]]
                if specific_key != "All" and specific_key not in mm_list:
                    return render_template("no_data.html", text="No Data")
            case "mmstats":
                title = f"{playername2}'s Mastermind"
                title_image = "https://cdn.legiontd2.com/icons/Mastermind.png"
                header_title = "MM"
                header_cdn = "https://cdn.legiontd2.com/icons/Items/"
                if specific_key == "All":
                    header_keys = ["Games", "Winrate", "Pickrate", "Player Elo", "W on 10"]
                    sub_headers = [["Best Opener", "Opener", "openstats"], ["Best Spell", "Spell", "spellstats"], ["Best Roll", "Rolls", "rollstats"]]
                elif specific_key == "Champion":
                    header_keys = ["Games", "Winrate", "Playrate"]
                    sub_headers = [["Champions", "Targets", "unitstats"], ["Openers", "Opener", "openstats"], ["Spells", "Spell", "spellstats"], ["Rolls", "Rolls", "rollstats"]]
                else:
                    header_keys = ["Games", "Winrate", "Playrate"]
                    sub_headers = [["Openers", "Opener", "openstats"], ["Spells", "Spell", "spellstats"], ["Rolls", "Rolls", "rollstats"]]
                if specific_key == "Megamind":
                    raw_data = drachbot.mmstats.mmstats(playerid, 0, elo, patch, "All", data_only=True, history_raw=history_raw)
                    games = raw_data[1]
                    avg_elo = raw_data[2]
                    raw_data = raw_data[0]
                else:
                    raw_data = drachbot.mmstats.mmstats(playerid, 0, elo, patch, specific_key, data_only=True, history_raw=history_raw)
                    games = raw_data[1]
                    avg_elo = raw_data[2]
                    raw_data = raw_data[0]
                if specific_key != "All" and specific_key not in mm_list:
                    return render_template("no_data.html", text="No Data")
            case "openstats":
                title = f"{playername2}'s Opener"
                title_image = "https://cdn.legiontd2.com/icons/Mastery/5.png"
                header_title = "Opener"
                header_cdn = "https://cdn.legiontd2.com/icons/"
                if specific_key == "All":
                    header_keys = ["Games", "Winrate", "Pickrate", "Player Elo", "W on 4"]
                    sub_headers = [["Best Add", "OpenWith", "unitstats"], ["Best MMs", "MMs", "mmstats"], ["Best Spell", "Spells", "spellstats"]]
                else:
                    header_keys = ["Games", "Winrate", "Playrate"]
                    sub_headers = [["Adds", "OpenWith", "unitstats"], ["MMs", "MMs", "mmstats"], ["Spells", "Spells", "spellstats"]]
                raw_data = drachbot.openstats.openstats(playerid, 0, elo, patch, unit=specific_key, data_only=True, history_raw=history_raw)
                games = raw_data[1]
                avg_elo = raw_data[2]
                raw_data = raw_data[0]
            case "spellstats":
                title = f"{playername2}'s Spell"
                title_image = "https://cdn.legiontd2.com/icons/LegionSpell.png"
                header_title = "Spell"
                header_cdn = "https://cdn.legiontd2.com/icons/"
                if specific_key == "All":
                    header_keys = ["Games", "Winrate", "Pickrate*", "Player Elo", "W on 10"]
                    sub_headers = [["Best Opener", "Opener", "openstats"], ["Best MMs", "MMs", "mmstats"]]
                else:
                    if specific_key in buff_spells:
                        header_keys = ["Games", "Winrate", "Playrate"]
                        sub_headers = [["Targets", "Targets", "unitstats"], ["Openers", "Opener", "openstats"], ["MMs", "MMs", "mmstats"]]
                    else:
                        header_keys = ["Games", "Winrate", "Playrate"]
                        sub_headers = [["Openers", "Opener", "openstats"], ["MMs", "MMs", "mmstats"]]
                raw_data = drachbot.spellstats.spellstats(playerid, 0, elo, patch, spellname=specific_key.lower(), data_only=True, history_raw=history_raw)
                games = raw_data[1]
                avg_elo = raw_data[2]
                raw_data = raw_data[0]
            case "unitstats":
                title = f"{playername2}'s Unit"
                title_image = "https://cdn.legiontd2.com/icons/Value10000.png"
                header_title = "Unit"
                header_cdn = "https://cdn.legiontd2.com/icons/"
                if specific_key == "All":
                    header_keys = ["Games", "Winrate", "Usage Rate", "Player Elo"]
                    sub_headers = [["Best Combo", "ComboUnit", "unitstats"], ["Best MMs", "MMs", "mmstats"], ["Best Spell", "Spells", "spellstats"]]
                else:
                    header_keys = ["Games", "Winrate", "Playrate"]
                    sub_headers = [["Combos", "ComboUnit", "unitstats"], ["MMs", "MMs", "mmstats"], ["Spells", "Spells", "spellstats"]]
                raw_data = drachbot.unitstats.unitstats(playerid, 0, elo, patch, unit=specific_key.lower(), data_only=True, history_raw=history_raw)
                games = raw_data[1]
                avg_elo = raw_data[2]
                raw_data = raw_data[0]
            case "rollstats":
                title = f"{playername2}'s Roll"
                title_image = "https://cdn.legiontd2.com/icons/Reroll.png"
                header_title = "Roll"
                header_cdn = "https://cdn.legiontd2.com/icons/"
                if specific_key == "All":
                    header_keys = ["Games", "Winrate", "Pickrate", "Player Elo"]
                    sub_headers = [["Best Combo", "ComboUnit", "rollstats"], ["Best MMs", "MMs", "mmstats"], ["Best Spell", "Spells", "spellstats"]]
                else:
                    header_keys = ["Games", "Winrate", "Playrate"]
                    sub_headers = [["Combos", "ComboUnit", "rollstats"], ["MMs", "MMs", "mmstats"], ["Spells", "Spells", "spellstats"]]
                raw_data = drachbot.unitstats.unitstats(playerid, 0, elo, patch, unit=specific_key.lower(), data_only=True, rollstats=True, history_raw=history_raw)
                games = raw_data[1]
                avg_elo = raw_data[2]
                raw_data = raw_data[0]
            case "wavestats":
                title = f"{playername2}'s Wave"
                title_image = "https://cdn.legiontd2.com/icons/LegionKing.png"
                header_title = "Wave"
                header_cdn = "https://cdn.legiontd2.com/icons/"
                if specific_key == "All":
                    header_keys = ["Endrate", "Sendrate", "Avg Leak"]
                    sub_headers = [["Best Merc", "Mercs", "mercstats"], ["Best Unit", "Units", "unitstats"]]
                else:
                    header_keys = ["Games", "Winrate", "Playrate"]
                    sub_headers = [["Mercs", "Mercs", "mercstats"], ["Units", "Units", "unitstats"]]
                raw_data = drachbot.wavestats.wavestats(playerid, 0, elo, patch, history_raw=history_raw)
                games = raw_data[1]
                avg_elo = raw_data[2]
                raw_data = raw_data[0]
        if type(raw_data) == str:
            return render_template("no_data.html", text="No Data")
        if raw_data:
            if stats != "mmstats" and stats != "megamindstats":
                new_dict = {}
                for key in raw_data:
                    if raw_data[key]["Count"] != 0:
                        new_dict[key] = raw_data[key]
                raw_data = new_dict
        if not raw_data or ((stats != "mmstats" and stats != "megamindstats") and specific_key != "All" and specific_key not in raw_data):
            return render_template("no_data.html", text="No Data")
        if stats == "megamindstats" and (specific_key != "All" and specific_key != "Megamind") and specific_key not in raw_data:
            return render_template("no_data.html", text="No Data")
        if stats == "mmstats" and specific_key != "Megamind":
            if specific_key != "All" and raw_data[specific_key]["Count"] == 0:
                return render_template("no_data.html", text="No Data")
        if specific_key == "All":
            html_file = "stats.html"
        else:
            html_file = "stats_specific.html"
        if stats == "wavestats":
            newIndex = sorted(raw_data, key=lambda x: raw_data[x]['EndCount'], reverse=True)
            raw_data = {k: raw_data[k] for k in newIndex}
        if specific_key != "All":
            specific_tier = True
        else:
            specific_tier = False
        elos = [2800, 2600, 2400, 2200, 2000, 1800, 1600, 1400, 1200, 1000]
        return render_template(html_file, data=raw_data, elo_brackets=elos, custom_winrate=util.custom_winrate,
                               games=games, avg_elo=avg_elo, patch=patch, patch_list=patches, elo=elo, custom_divide=util.custom_divide,
                               human_format=util.human_format, get_perf_list=util.get_perf_list, get_dict_value=util.get_dict_value,
                               specific_key=specific_key, get_unit_name=util.get_unit_name, sort_dict=util.sort_dict, title=title, title_image=title_image,
                               stats=stats, header_cdn=header_cdn, header_title=header_title, header_keys=header_keys, get_key_value=util.get_key_value,
                               sub_headers=sub_headers, get_cdn_image=util.get_cdn_image, mm_list=mm_list, get_tooltip=util.get_tooltip,
                               data_keys=raw_data.keys(), get_rank_url=util.get_rank_url, get_avg_end_wave=util.get_avg_end_wave, specific_tier=specific_tier,
                               playerurl = f"/profile/{playername}/", playername2=f"{playername2} ", patch_selector=True, playerprofile = True)

@app.route('/<stats>/', defaults={"elo": defaults[1], "patch": defaults[0], "specific_key": "All"})
@app.route('/<stats>/<patch>/<elo>/', defaults={"specific_key": "All"})
@app.route('/<stats>/<patch>/<elo>/<specific_key>')
@cache.cached(timeout=timeout)
def stats(stats, elo, patch, specific_key):
    playername2=""
    if stats not in ["mmstats", "openstats", "spellstats", "unitstats", "megamindstats", "rollstats", "wavestats"]:
        return render_template("no_data.html", text="No Data")
    raw_data = None
    match stats:
        case "megamindstats":
            header_title = "MM"
            header_cdn = "https://cdn.legiontd2.com/icons/Items/"
            title = "Megamind"
            title_image = "https://cdn.legiontd2.com/icons/Items/Megamind.png"
            folder = "megamindstats"
            if specific_key == "Megamind":
                specific_key = "All"
            if specific_key == "All":
                header_keys = ["Tier", "Games", "Winrate", "Playrate", "Player Elo", "W on 10"]
                sub_headers = [["Best Opener", "Opener", "openstats"], ["Best Spell", "Spell", "spellstats"], ["Best Roll", "Rolls", "rollstats"]]
            elif specific_key == "Champion":
                header_keys = ["Tier", "Games", "Winrate", "Playrate"]
                sub_headers = [["Champions", "Targets", "unitstats"],["Openers", "Opener", "openstats"], ["Spells", "Spell", "spellstats"], ["Rolls", "Rolls", "rollstats"]]
            else:
                header_keys = ["Tier", "Games", "Winrate", "Playrate"]
                sub_headers = [["Openers", "Opener", "openstats"], ["Spells", "Spell", "spellstats"], ["Rolls", "Rolls", "rollstats"]]
            if specific_key != "All" and specific_key not in mm_list:
                return render_template("no_data.html", text="No Data")
        case "mmstats":
            title = "Mastermind"
            title_image = "https://cdn.legiontd2.com/icons/Mastermind.png"
            header_title = "MM"
            header_cdn = "https://cdn.legiontd2.com/icons/Items/"
            if specific_key == "All":
                header_keys = ["Tier", "Games", "Winrate", "Pickrate", "Player Elo", "W on 10"]
                sub_headers = [["Best Opener", "Opener", "openstats"], ["Best Spell", "Spell", "spellstats"], ["Best Roll", "Rolls", "rollstats"]]
            elif specific_key == "Champion":
                header_keys = ["Tier", "Games", "Winrate", "Playrate"]
                sub_headers = [["Champions", "Targets", "unitstats"],["Openers", "Opener", "openstats"], ["Spells", "Spell", "spellstats"], ["Rolls", "Rolls", "rollstats"]]
            else:
                header_keys = ["Tier", "Games", "Winrate", "Playrate"]
                sub_headers = [["Openers", "Opener", "openstats"], ["Spells", "Spell", "spellstats"], ["Rolls", "Rolls", "rollstats"]]
            folder = "mmstats"
            if specific_key != "All" and specific_key not in mm_list:
                return render_template("no_data.html", text="No Data")
        case "openstats":
            title = "Opener"
            title_image = "https://cdn.legiontd2.com/icons/Mastery/5.png"
            header_title = "Opener"
            header_cdn = "https://cdn.legiontd2.com/icons/"
            if specific_key == "All":
                header_keys = ["Tier", "Games", "Winrate", "Pickrate", "Player Elo", "W on 4"]
                sub_headers = [["Best Add", "OpenWith", "unitstats"], ["Best MMs", "MMs", "mmstats"], ["Best Spell", "Spells", "spellstats"]]
            else:
                header_keys = ["Tier", "Games", "Winrate", "Playrate"]
                sub_headers = [["Adds", "OpenWith", "unitstats"], ["MMs", "MMs", "mmstats"], ["Spells", "Spells", "spellstats"]]
            folder = "openstats"
        case "spellstats":
            title = "Spell"
            title_image = "https://cdn.legiontd2.com/icons/LegionSpell.png"
            header_title = "Spell"
            header_cdn = "https://cdn.legiontd2.com/icons/"
            if specific_key == "All":
                header_keys = ["Tier", "Games", "Winrate", "Pickrate*", "Player Elo", "W on 10"]
                sub_headers = [["Best Opener", "Opener", "openstats"], ["Best MMs", "MMs", "mmstats"]]
            else:
                if specific_key in buff_spells:
                    header_keys = ["Tier", "Games", "Winrate", "Playrate"]
                    sub_headers = [["Targets", "Targets", "unitstats"], ["Openers", "Opener", "openstats"], ["MMs", "MMs", "mmstats"]]
                else:
                    header_keys = ["Tier", "Games", "Winrate", "Playrate"]
                    sub_headers = [["Openers", "Opener", "openstats"], ["MMs", "MMs", "mmstats"]]
            folder = "spellstats"
        case "unitstats":
            title = "Unit"
            title_image = "https://cdn.legiontd2.com/icons/Value10000.png"
            header_title = "Unit"
            header_cdn = "https://cdn.legiontd2.com/icons/"
            if specific_key == "All":
                header_keys = ["Tier", "Games", "Winrate", "Usage Rate", "Player Elo"]
                sub_headers = [["Best Combo", "ComboUnit", "unitstats"], ["Best MMs", "MMs", "mmstats"], ["Best Spell", "Spells", "spellstats"]]
            else:
                header_keys = ["Tier", "Games", "Winrate", "Playrate"]
                sub_headers = [["Combos", "ComboUnit", "unitstats"], ["MMs", "MMs", "mmstats"], ["Spells", "Spells", "spellstats"]]
            folder = "unitstats"
        case "rollstats":
            title = "Roll"
            title_image = "https://cdn.legiontd2.com/icons/Reroll.png"
            header_title = "Roll"
            header_cdn = "https://cdn.legiontd2.com/icons/"
            if specific_key == "All":
                header_keys = ["Tier", "Games", "Winrate", "Pickrate", "Player Elo"]
                sub_headers = [["Best Combo", "ComboUnit", "rollstats"], ["Best MMs", "MMs", "mmstats"], ["Best Spell", "Spells", "spellstats"]]
            else:
                header_keys = ["Tier", "Games", "Winrate", "Playrate"]
                sub_headers = [["Combos", "ComboUnit", "rollstats"], ["MMs", "MMs", "mmstats"], ["Spells", "Spells", "spellstats"]]
            folder = "rollstats"
        case "wavestats":
            title = "Wave"
            title_image = "https://cdn.legiontd2.com/icons/LegionKing.png"
            header_title = "Wave"
            header_cdn = "https://cdn.legiontd2.com/icons/"
            if specific_key == "All":
                header_keys = ["Endrate", "Sendrate", "Avg Leak"]
                sub_headers = [["Best Merc", "Mercs", "mercstats"], ["Best Unit", "Units", "unitstats"]]
            else:
                header_keys = ["Games", "Winrate", "Playrate"]
                sub_headers = [["Mercs", "Mercs", "mercstats"], ["Units", "Units", "unitstats"]]
            folder = "wavestats"
    for file in os.listdir(shared_folder+f"data/{folder}/"):
        if file.startswith(f"{patch}_{elo}"):
            games = file.split("_")[2]
            if games == "o":
                return render_template("no_data.html", text="No Data")
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
        return render_template("no_data.html", text="No Data")
    if stats == "megamindstats" and (specific_key != "All" and specific_key != "Megamind") and specific_key not in raw_data:
        return render_template("no_data.html", text="No Data")
    if stats == "mmstats" and specific_key != "Megamind":
        if specific_key != "All" and raw_data[specific_key]["Count"] == 0:
            return render_template("no_data.html", text="No Data")
    if specific_key == "All":
        html_file = "stats.html"
    else:
        html_file = "stats_specific.html"
    if stats == "wavestats":
        newIndex = sorted(raw_data, key=lambda x: raw_data[x]['EndCount'], reverse=True)
        raw_data = {k: raw_data[k] for k in newIndex}
    if specific_key != "All":
        specific_tier = True
    else:
        specific_tier = False
    return render_template(html_file, data=raw_data, elo_brackets=elos, custom_winrate=util.custom_winrate,
                           games=games, avg_elo = avg_elo, patch = patch, patch_list=patches, elo = elo, custom_divide = util.custom_divide,
                           human_format= util.human_format, get_perf_list=util.get_perf_list, get_dict_value=util.get_dict_value,
                           specific_key=specific_key, get_unit_name=util.get_unit_name, sort_dict=util.sort_dict, title=title, title_image=title_image,
                           stats=stats, header_cdn=header_cdn, header_title=header_title, header_keys=header_keys, get_key_value=util.get_key_value,
                           sub_headers=sub_headers, get_cdn_image=util.get_cdn_image, mm_list=mm_list, mod_date=mod_date, get_tooltip=util.get_tooltip,
                           data_keys = raw_data.keys(), get_rank_url=util.get_rank_url, get_avg_end_wave=util.get_avg_end_wave, specific_tier=specific_tier,
                           playerurl = "", playername2=playername2, patch_selector = False)

if platform.system() == "Windows":
    app.run(host="0.0.0.0", debug=True)
else:
    from waitress import serve
    scheduler.add_job(id = 'Scheduled Task', func=leaderboard_task, trigger="interval", seconds=300)
    scheduler.start()
    serve(app, host="0.0.0.0", port=54937)