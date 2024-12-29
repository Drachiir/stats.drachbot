import os
import platform
import json
from datetime import datetime, timezone, timedelta
from flask_caching import Cache
from flask import Flask, render_template, redirect, url_for, send_from_directory, request, session, jsonify
import re
import drachbot.legion_api as legion_api
import drachbot.drachbot_db as drachbot_db
import drachbot.mmstats
import drachbot.openstats
import drachbot.spellstats
import drachbot.unitstats
import drachbot.wavestats
import drachbot.gamestats
import util
from drachbot.peewee_pg import GameData, PlayerData
from util import get_rank_url, custom_winrate, plus_prefix, custom_divide, get_gamestats_values, human_format, clean_unit_name
from flask_apscheduler import APScheduler
from playfab import PlayFabClientAPI, PlayFabSettings
from flask_cors import CORS, cross_origin
import time
import threading
from threading import Thread
from drachbot.peewee_pg import PlayerProfile
from peewee import fn
import msgpack

cache = Cache()

app = Flask(__name__)
app.secret_key = 'python>js'

CORS(app, resources={r"/api/*": {"origins": "*"}})  # Enable CORS for all

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

def get_playfab_stats(playfabid, result_count = 1):
    PlayFabSettings.TitleId = "9092"
    login_request = {
        "TitleId": "9092",
        "CustomId": "LTD2Website",
        "CreateAccount": False
    }
    stats_request = {
        "PlayFabId": playfabid,
        "StatisticName": "overallElo",
        "MaxResultsCount": result_count,
        "ProfileConstraints": {
            "ShowDisplayName": True,
            "ShowStatistics": True,
            "ShowLocations": True,
            "ShowAvatarUrl": True,
            "ShowContactEmailAddresses": True
        }
    }
    result_event = threading.Event()
    result = None
    
    def callback(success, failure):
        nonlocal result
        if success:
            result = success
        else:
            result = None
        result_event.set()
    
    PlayFabClientAPI.LoginWithCustomID(login_request, callback)
    result_event.wait()
    if result is None:
        return None
    result_event.clear()
    
    PlayFabClientAPI.GetLeaderboardAroundPlayer(stats_request, callback)
    result_event.wait()
    return result

def get_profile_from_playfab(playername:str):
    PlayFabSettings.TitleId = "9092"
    login_request = {
        "TitleId": "9092",
        "CustomId": "LTD2Website",
        "CreateAccount": False
    }
    playfab_request = {
        "TitleDisplayName": playername
    }
    
    result_event = threading.Event()
    result = None
    
    def callback(success, failure):
        nonlocal result
        if success:
            result = success
        else:
            result = None
        result_event.set()
    
    PlayFabClientAPI.LoginWithCustomID(login_request, callback)
    result_event.wait()
    if result is None:
        return None
    result_event.clear()
    
    PlayFabClientAPI.GetAccountInfo(playfab_request, callback)
    result_event.wait()
    return result


def get_player_profile(playername):
    playerid = playername if len(playername) > 13 and re.fullmatch(r'[0-9A-F]+', playername) else None
    api_profile = legion_api.getprofile(playerid or playername, by_id=bool(playerid))
    if api_profile in [0, 1]:
        playfab_profile = get_profile_from_playfab(playername)
        if playfab_profile:
            playerid = playfab_profile["AccountInfo"]["PlayFabId"]
            api_profile = {"playerName": playfab_profile["AccountInfo"]["TitleInfo"]["DisplayName"],
                           "avatarUrl": playfab_profile["AccountInfo"]["TitleInfo"]["AvatarUrl"],
                           "guildTag": ""}
        else:
            playerid = drachbot_db.get_playerid(playername) if not playerid else None
            api_profile = {"playerName": playername, "avatarUrl": "icons/DefaultAvatar.png", "guildTag": ""}
        if not playerid:
            return None
    else:
        playerid = api_profile["_id"]
    
    return {"playerid": playerid, "api_profile": api_profile}


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

@app.route('/terms-of-service.txt/')
def tos():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'terms-of-service.txt', mimetype='text/plain')

@app.route('/privacy-policy.txt/')
def privacy_policy():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'privacy-policy.txt', mimetype='text/plain')

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
website_stats = defaults_json["StatCategories"]

@app.route("/api/defaults")
def api_defaults():
    return defaults_json

@app.route("/")
@cache.cached(timeout=timeout)
def home():
    folder_list = ["mmstats", "openstats", "spellstats", "rollstats", "unitstats", "wavestats"]
    header_list = ["MM", "Open", "Spell", "Roll", "Unit", "Wave"]
    title_list = ["MM Stats", "Opener Stats", "Spell Stats", "Roll Stats", "Unit Stats", "Wave Stats"]
    image_list =["https://cdn.legiontd2.com/icons/Mastermind.png", "https://cdn.legiontd2.com/icons/Mastery/5.png"
                 ,"https://cdn.legiontd2.com/icons/LegionSpell.png", "https://cdn.legiontd2.com/icons/Reroll.png"
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
        if temp_string[0] == defaults[0] and temp_string[1] == str(defaults[1]):
            total_games = util.human_format(int(temp_string[2]))
            break
    return render_template("home.html", data_list=data_list, image_list=image_list, keys=keys,
                           elo=defaults[1], patch=defaults[0], get_cdn_image = util.get_cdn_image, get_key_value=util.get_key_value,
                           total_games=total_games, get_tooltip = util.get_tooltip, home=True)

@app.route('/classicmodes')
@cache.cached(timeout=60)
def classic_modes():
    increment_in_seconds = 3.25 * 60 * 60
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

@app.route("/leaderboard", defaults={"playername": None})
@app.route("/leaderboard/<playername>")
def leaderboard(playername):
    if not playername:
        api_profile = None
        with open("leaderboard.json", "r") as f:
            leaderboard_data = json.load(f)
    else:
        stats = get_player_profile(playername)
        if not stats:
            return render_template("no_data.html", text=f"Player { playername } not found.")
        player_id = stats["playerid"]
        api_profile = stats["api_profile"]
        leaderboard_data = get_playfab_stats(player_id, 100)
    if not leaderboard_data:
        return render_template("no_data.html", text=f"Error loading leaderboard, try again later.")
    return render_template("leaderboard.html", leaderboard = leaderboard_data, get_rank_url=util.get_rank_url, get_value=util.get_value_playfab,
                           winrate = util.custom_winrate, api_profile=api_profile)

@app.route("/rank-distribution/", methods=['GET'], defaults={'snapshot': defaults_json["RankDistributionDate"]})
@app.route("/rank-distribution/<snapshot>", methods=['GET'])
def rank_distribution(snapshot):
    try:
        min_games = int(request.args.get('min_games', 1))
    except Exception:
        min_games = 1
    try:
        min_winrate = int(request.args.get('min_winrate', 0))
    except Exception:
        min_winrate = 0
    with open(f"{shared_folder}/leaderboard/leaderboard_parsed_{snapshot}.json", "r") as f:
        leaderboard_data = json.load(f)
    snapshots_list = []
    for ss in os.listdir(f"{shared_folder}/leaderboard"):
        snapshots_list.append(ss.split("_")[2].replace(".json", ""))
    snapshots_list = sorted(snapshots_list, key=lambda x: int(x.split("-")[1]+x.split("-")[0]), reverse=True)
    return render_template("rank-distribution.html", min_games=min_games, leaderboard_data=leaderboard_data, min_winrate=min_winrate,
                           snapshots_list=snapshots_list)

@app.route('/wave-distribution/', defaults={"elo": defaults[1], "patch": defaults[0]})
@app.route('/wave-distribution/<patch>/', defaults={"elo": defaults[1]})
@app.route('/wave-distribution/<patch>/<elo>/')
def wave_distribution(patch, elo):
    for datajson in os.listdir(f"{shared_folder}/data/wavestats/"):
        if datajson.startswith(f"{patch}_{elo}"):
            with open(f"{shared_folder}/data/wavestats/{datajson}", "r") as f:
                wave_data = json.load(f)
                games = datajson.split("_")[2]
                avg_elo = datajson.split("_")[3].split(".")[0]
                break
    else:
        return render_template("no_data.html", text=f"No data.")
    return render_template("wave-distribution.html", wave_data=wave_data, patch=patch, elo= elo, games= games,
                           avg_elo=avg_elo, patch_list=patches, elos=elos, get_rank_url=util.get_rank_url, get_avg_end_wave=util.get_avg_end_wave,
                           human_format=util.human_format)

@app.route('/proleaks/', defaults= {"wave": 1, "patch": defaults[0]})
@app.route('/proleaks/<wave>', defaults= {"patch": defaults[0]})
@app.route('/proleaks/<wave>/<patch>')
@cache.cached(timeout=timeout)
def proleaks(wave, patch):
    for datajson in os.listdir(f"{shared_folder}/data/proleaks/"):
        if datajson.startswith(f"{patch}"):
            games = datajson.split("_")[2]
            try:
                games = int(games)
            except Exception:
                return render_template("no_data.html", text="No Data")
            avg_elo = datajson.split("_")[3].replace(".json", "")
            with open(f"{shared_folder}/data/proleaks/{datajson}", "r") as f:
                mod_date = util.time_ago(datetime.fromtimestamp(os.path.getmtime(f"{shared_folder}/data/proleaks/{datajson}")).timestamp())
                data = json.load(f)
                break
    else:
        return render_template("no_data.html", text=f"No data.")
    return render_template("proleaks.html", proleak_data = data[f"Wave{wave}"], wave=wave, get_cdn=util.get_cdn_image, get_rank_url=util.get_rank_url,
                           const_file = util.const_file, plus_prefix = util.plus_prefix, games=games, avg_elo=avg_elo, patch_name = patch, human_format = util.human_format,
                           clean_unit_name = util.clean_unit_name, patch_list = patches, wave_string = f"Wave{wave}", mod_date=mod_date)


@app.route("/api/livegames/", defaults={"playername": None})
@app.route("/api/livegames/<playername>")
def livegames_api(playername):
    games = []
    for game in os.listdir(shared_folder_live):
        try:
            with open(f"{shared_folder_live}/{game}", "r", encoding="utf_8") as f2:
                txt = f2.readlines()
                f2.close()
            path2 = f"{shared_folder_live}/{game}"
            mod_date = datetime.fromtimestamp(os.path.getmtime(path2), tz=timezone.utc).timestamp()
            game_elo = txt[-1]
            west_players = [txt[0].replace("\n", "").split(":"), txt[1].replace("\n", "").split(":")]
            east_players = [txt[2].replace("\n", "").split(":"), txt[3].replace("\n", "").split(":")]
            if not playername:
                games.append([mod_date, game_elo, west_players, east_players])
            elif (any(playername.lower() in [p.lower() for p in sublist] for sublist in west_players)
                  or any(playername.lower() in [p.lower() for p in sublist] for sublist in east_players)):
                return [mod_date, game_elo, west_players, east_players]
        except Exception:
            continue
    games = sorted(games, key=lambda x: int(x[1]), reverse=True)
    return games

@app.route("/api/drachbot_reroll_overlay/<rank>/<roll>")
@cross_origin()
def drachbot_reroll_overlay_api(rank, roll):
    data_list = os.listdir(f"{shared_folder}/data/rollstats")
    roll_data = {}
    for file in data_list:
        string_list = file.split("_")
        if string_list[0] == defaults[0] and string_list[1] == rank:
            with open(f"{shared_folder}/data/rollstats/{file}", "r") as f:
                roll_data = json.load(f)
            break
    if roll.lower() in roll_data:
        return [round(roll_data[roll.lower()]["Count"]/int(string_list[2])*100, 1), round(roll_data[roll.lower()]["Wins"]/roll_data[roll.lower()]["Count"]*100, 1)]
    return roll_data
    
@app.route("/api/drachbot_overlay/<playername>")
@cross_origin()
def drachbot_overlay_api(playername):
    # if playername == "TestData123":
    #     with open("exampledata.json", "r") as f:
    #         return json.load(f)
    playerid = drachbot_db.get_playerid(playername)
    if not playerid:
        api_profile = legion_api.getprofile(playername)
        if api_profile in [0, 1]:
            return {"Error": "Player not found"}
        playerid = api_profile["_id"]
    req_columns = [
        [GameData.game_id, GameData.queue, GameData.date, GameData.version, GameData.ending_wave, GameData.game_elo, GameData.player_ids,
         PlayerData.player_id, PlayerData.player_name, PlayerData.player_slot, PlayerData.player_elo, PlayerData.game_result, PlayerData.elo_change,
         PlayerData.legion, PlayerData.mercs_sent_per_wave, PlayerData.kingups_sent_per_wave, PlayerData.megamind],
        ["game_id", "date", "version", "ending_wave", "game_elo"],
        ["player_id", "player_name", "player_slot", "player_elo", "game_result", "elo_change", "legion", "mercs_sent_per_wave", "kingups_sent_per_wave", "megamind"]]
    history = drachbot_db.get_matchistory(playerid, 20, earlier_than_wave10=True, req_columns=req_columns, skip_stats=True)
    if not history:
        history = drachbot_db.get_matchistory(playerid, 20, earlier_than_wave10=True, req_columns=req_columns, skip_stats=True, get_new_games=True)
    winlose = {"Wins": 0, "Losses": 0}
    elochange = 0
    mms = {}
    wave1 = {"UpgradeKingAttack": 0, "Snail": 0, "Mythium32": 0}
    for game in history:
        for player in game["players_data"]:
            if player["player_id"] == playerid:
                # Fav MM
                if player["megamind"]:
                    player["legion"] = "Megamind"
                if player["legion"] in mms:
                    mms[player["legion"]] += 1
                else:
                    mms[player["legion"]] = 1
                # Wave 1 Tendency
                if player["mercs_sent_per_wave"][0].split("!")[0] == "Snail":
                    wave1["Snail"] += 1
                elif str(player["kingups_sent_per_wave"][0].split("!")[0]).startswith("Upgrade"):
                    wave1["UpgradeKingAttack"] += 1
                else:
                    wave1["Mythium32"] += 1
                if player["game_result"] == "won":
                    elochange += player["elo_change"]
                    winlose["Wins"] += 1
                else:
                    elochange += player["elo_change"]
                    winlose["Losses"] += 1
    return {"Masterminds": mms, "Wave1": wave1, "WinLose": winlose, "EloChange": elochange, "String": f"Last {len(history)} Games"}

@app.route("/gameviewer/<gameid>", defaults={"wave": 1})
@app.route("/gameviewer/<gameid>/<wave>")
def gameviewer(gameid, wave):
    data = drachbot.drachbot_db.get_game_by_id(gameid)
    player_map = {0: 1, 1: 0, 2: 3, 3: 2}
    if data == {"Error": "Game not found."}:
        return render_template("no_data.html", text="Game ID not found/valid")
    return render_template("gameviewer.html", game_data = data, game_viewer = True, get_cdn=util.get_cdn_image, get_rank_url=util.get_rank_url,
                           const_file = util.const_file, plus_prefix = util.plus_prefix, wave=wave, player_map=player_map)
    
@app.route("/livegames")
def livegames():
    return render_template("livegames.html", get_rank_url=get_rank_url, livegames = True)

player_refresh_state = {}
COOLDOWN_PERIOD = 300

def request_games(playerid, limit):
    drachbot_db.get_games_loop(playerid, 0, 500, timeout_limit=limit)
    player_refresh_state[playerid]['in_progress'] = False
    player_refresh_state[playerid]['cooldown_start_time'] = datetime.now(tz=timezone.utc)

def get_remaining_cooldown(playerid):
    state = player_refresh_state.get(playerid, {})
    cooldown_start = state.get('cooldown_start_time')
    
    if not cooldown_start:
        return 0
    
    elapsed_time = (datetime.now(tz=timezone.utc) - cooldown_start).total_seconds()
    remaining_cooldown = max(0, COOLDOWN_PERIOD - elapsed_time)
    
    return remaining_cooldown

@app.route("/api/request_games/<playername>", defaults={"limit": 2})
@app.route("/api/request_games/<playername>/<limit>")
def request_games_api(playername, limit):
    limit = int(limit)
    limit = 5 if limit > 5 else limit
    if len(playername) > 13 and re.fullmatch(r'[0-9A-F]+', playername):
        playerid = playername
    else:
        api_profile = legion_api.getprofile(playername)
        if api_profile in [0, 1]:
            return {"error": "Player not found"}
        playerid = api_profile["_id"]
    if playerid not in player_refresh_state:
        player_refresh_state[playerid] = {'in_progress': False, 'cooldown_start_time': None}
    
    state = player_refresh_state[playerid]
    remaining_cooldown = get_remaining_cooldown(playerid)
    if state['in_progress']:
        return jsonify({"error": "Refresh already in progress"}), 400
    if remaining_cooldown > 0:
        return jsonify({"error": f"Refresh on cooldown for {round(remaining_cooldown/60, 1)} minutes"}), 400
    
    state['in_progress'] = True
    state['cooldown'] = 0
    thread = Thread(target=request_games, args=(playerid, limit,))
    thread.start()
    return jsonify({"message": "Refresh started"})
    
@app.route('/api/check_refresh_status/<playerid>')
def check_refresh_status(playerid):
    state = player_refresh_state.get(playerid, {'in_progress': False, 'cooldown_start_time': None})
    cooldown_duration = get_remaining_cooldown(playerid)
    return jsonify({
        'in_progress': state.get('in_progress', False),
        'cooldown': cooldown_duration
    })

@app.route('/api/get_search_results/', methods=['GET'], defaults={"search_term": ""})
@app.route('/api/get_search_results/<search_term>', methods=['GET'])
def get_search_results(search_term):
    query = (PlayerProfile
             .select(PlayerProfile.player_name, PlayerProfile.avatar_url)
             .where(fn.LOWER(PlayerProfile.player_name).contains(search_term.lower()))
             .limit(5))

    players = [{'player_name': player.player_name,
                'avatar_url': player.avatar_url}
               for player in query]
    return jsonify(players), 200

@app.route('/api/get_player_stats/<playername>', methods=['GET'])
def get_player_stats(playername):
    playerid = drachbot_db.get_playerid(playername)
    if not playerid:
        api_profile = legion_api.getprofile(playername)
        if api_profile in [0, 1]:
            return jsonify({"Statsus": "Not Found"}), 400
        else:
            playerid = api_profile["_id"]
    api_stats = legion_api.getstats(playerid)
    return api_stats

@app.route('/api/get_player_matchhistory/<playername>/<playerid>/<patch>/<page>', methods=['GET'])
def get_player_matchhistory(playername, playerid, patch, page):
    path = f"Files/player_cache/{playername}_profile_{patch}.msgpack"
    try:
        with open(path, "rb") as f:
            history = msgpack.unpackb(f.read(), raw=False)
    except FileNotFoundError:
        req_columns = [
            [GameData.game_id, GameData.queue, GameData.date, GameData.version, GameData.ending_wave, GameData.game_elo, GameData.player_ids, GameData.game_length,
             PlayerData.player_id, PlayerData.player_name, PlayerData.player_elo, PlayerData.player_slot, PlayerData.game_result, PlayerData.elo_change,
             PlayerData.legion, PlayerData.mercs_sent_per_wave, PlayerData.kingups_sent_per_wave, PlayerData.opener, PlayerData.megamind, PlayerData.spell,
             PlayerData.workers_per_wave, PlayerData.mvp_score, PlayerData.party_size],
            ["game_id", "date", "version", "ending_wave", "game_elo", "game_length"],
            ["player_id", "player_name", "player_elo", "player_slot", "game_result", "elo_change", "legion",
             "mercs_sent_per_wave", "kingups_sent_per_wave", "opener", "megamind", "spell", "workers_per_wave", "mvp_score", "party_size"]]
        history = drachbot_db.get_matchistory(playerid, 0, 0, patch, earlier_than_wave10=True, req_columns=req_columns, skip_stats=True)
        try:
            os.remove(path)
        except Exception:
            pass
        with open(path, "wb") as f:
            f.write(msgpack.packb(history, default=str))
    history_parsed = []
    slice_int = 20*int(page)
    player_map = {1: [1, 2, 3], 2: [0, 2, 3], 5: [3, 0, 1], 6: [2, 0, 1]}
    for game in history[slice_int:][:20]:
        if type(game["date"]) == str:
            game["date"] = datetime.strptime(game["date"].split(" ")[0], "%Y-%m-%d")
        end_wave_cdn = util.get_cdn_image(str(game["ending_wave"]), "Wave")
        temp_dict = {"EndWave": end_wave_cdn, "Result_String": "", "Version": game["version"], "EloChange": ""
            , "Date": game["date"], "gamelink": f"/gameviewer/{game["game_id"]}",
                     "time_ago": util.time_ago(game["date"]), "players_data": [], "Opener": "", "Mastermind": "", "Spell": "",
                     "Worker": "", "Megamind": False, "MVP": False}
        for player in game["players_data"]:
            temp_dict["players_data"].append([player["player_name"], player["player_elo"], player["party_size"]])
            if player["player_id"] == playerid:
                teammate = game["players_data"][player_map[player["player_slot"]][0]]
                if player["mvp_score"] > teammate["mvp_score"]:
                    temp_dict["MVP"] = True
                # Match history details
                temp_dict["Opener"] = player["opener"]
                temp_dict["Mastermind"] = player["legion"]
                try:
                    temp_dict["Spell"] = player["spell"]
                except KeyError:
                    temp_dict["Spell"] = "None"
                if player["megamind"]:
                    temp_dict["Megamind"] = True
                temp_dict["Worker"] = round(player["workers_per_wave"][-1], 1)
                temp_dict["EloChange"] = util.plus_prefix(player["elo_change"])
                if player["game_result"] == "won":
                    won = True
                else:
                    won = False
                temp_dict["Result_String"] = [won, f"Wave {game["ending_wave"]}"]
        history_parsed.append(temp_dict)
    if not history_parsed:
        return "No data found", 404
    return history_parsed

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
        #get player profile
        result = get_player_profile(playername)
        if not result:
            return render_template("no_data.html", text=f"{playername} not found.")
        playerid = result["playerid"]
        api_profile = result["api_profile"]
        # Get player stats
        in_progress = player_refresh_state.get(playerid, {}).get('in_progress', False)
        cooldown_duration = get_remaining_cooldown(playerid)
        api_stats = {}
        playfab_stats = None
        max_retries = 2
        attempt = 0
        while not playfab_stats and attempt < max_retries:
            try:
                playfab_stats = get_playfab_stats(playerid)
            except Exception:
                pass
            attempt += 1
        if playfab_stats:
            player = playfab_stats["Leaderboard"][0]
            try:
                api_profile["playerName"] = player["DisplayName"]
            except Exception:
                api_profile["playerName"] = playername
            try:
                api_profile["avatarUrl"] = player["Profile"]["AvatarUrl"]
            except Exception:
                api_profile["avatarUrl"] = "icons/DefaultAvatar.png"
            try:
                api_profile["guildTag"] = player["Profile"]["ContactEmailAddresses"][0]["EmailAddress"].split("_")[1].split("+")[1]
            except Exception:
                api_profile["guildTag"] = ""
            for stat_key, version in [("rankedWinsThisSeason", 8), ("rankedLossesThisSeason", 8), ("overallElo", 11), ("overallPeakEloThisSeason", 11)]:
                try:
                    api_stats[stat_key] = util.get_value_playfab(player["Profile"]["Statistics"], stat_key, version=version)
                except Exception:
                    api_stats[stat_key] = 0
            try:
                avatar_stacks = int(player["Profile"]["ContactEmailAddresses"][0]["EmailAddress"].split("_")[5].replace("@x.x", "").split("+")[1])
            except Exception:
                avatar_stacks = 0
            api_stats["avatarBorder"] = util.get_avatar_border(avatar_stacks)
            try:
                api_stats["flag"] = player["Profile"]["Locations"][0]["CountryCode"]
            except Exception:
                api_stats["flag"] = ""
            countries = util.COUNTRIES_CACHE
            if type(countries["countries"][player["Profile"]["Locations"][0]["CountryCode"]]) == list:
                api_stats["Country"] = countries["countries"][player["Profile"]["Locations"][0]["CountryCode"]][0]
            else:
                api_stats["Country"] = countries["countries"][player["Profile"]["Locations"][0]["CountryCode"]]
            player_rank = f"Rank #{player["Position"]+1}"
        else:
            api_stats = legion_api.getstats(playerid)
            api_stats["avatarBorder"] = ""
            api_stats["flag"] = ""
            api_stats["Country"] = ""
            player_rank = ""
        try:
            _ = api_stats["rankedWinsThisSeason"]
            _ = api_stats["rankedLossesThisSeason"]
            _ = api_stats["overallElo"]
            _ = api_stats["overallPeakEloThisSeason"]
        except KeyError:
            return render_template("no_data.html", text=f"{playername} not found.")
        if not api_stats["rankedWinsThisSeason"]:
            api_stats["rankedWinsThisSeason"] = 0
        if not api_stats["rankedLossesThisSeason"]:
            api_stats["rankedLossesThisSeason"] = 0
        stats_list = website_stats
        image_list = [
            "https://cdn.legiontd2.com/icons/Mastermind.png",
            "https://cdn.legiontd2.com/icons/Items/Megamind.png",
            "https://cdn.legiontd2.com/icons/Mastery/5.png",
            "https://cdn.legiontd2.com/icons/LegionSpell.png",
            "https://cdn.legiontd2.com/icons/Reroll.png",
            "https://cdn.legiontd2.com/icons/Value10000.png",
            "https://cdn.legiontd2.com/icons/LegionKing.png",
            "https://cdn.legiontd2.com/icons/DefaultAvatar.png"
        ]
        path = f"Files/player_cache/{api_profile["playerName"]}_profile_{patch}.msgpack"
        history = None
        if os.path.isfile(path) and cooldown_duration == 0:
            mod_date = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)
            date_diff = datetime.now(tz=timezone.utc) - mod_date
            minutes_diff = date_diff.total_seconds() / 60
            if minutes_diff > 10:
                os.remove(path)
            else:
                with open(path, "rb") as f:
                    history = msgpack.unpackb(f.read(), raw=False)
        if not history:
            req_columns = [
                [GameData.game_id, GameData.queue, GameData.date, GameData.version, GameData.ending_wave, GameData.game_elo, GameData.player_ids, GameData.game_length,
                 PlayerData.player_id, PlayerData.player_name, PlayerData.player_elo, PlayerData.player_slot, PlayerData.game_result, PlayerData.elo_change,
                 PlayerData.legion, PlayerData.mercs_sent_per_wave, PlayerData.kingups_sent_per_wave, PlayerData.opener, PlayerData.megamind, PlayerData.spell,
                 PlayerData.workers_per_wave, PlayerData.mvp_score, PlayerData.party_size],
                ["game_id", "date", "version", "ending_wave", "game_elo", "game_length"],
                ["player_id", "player_name", "player_elo", "player_slot", "game_result", "elo_change", "legion",
                 "mercs_sent_per_wave", "kingups_sent_per_wave", "opener", "megamind", "spell", "workers_per_wave", "mvp_score", "party_size"]]
            skip_game_refresh = True if api_stats["overallElo"] > 1750 else False
            history = drachbot_db.get_matchistory(playerid, 0, elo, patch, earlier_than_wave10=True, req_columns=req_columns,
                                                  playerstats=api_stats, playerprofile=api_profile, pname=playername, skip_game_refresh=skip_game_refresh)
            try:
                os.remove(path)
            except Exception:
                pass
            with open(path, "wb") as f:
                f.write(msgpack.packb(history, default=str))
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
        mvp_count = 0
        for game in history:
            if type(game["date"]) == str:
                game["date"] = datetime.strptime(game["date"].split(" ")[0], "%Y-%m-%d")
            end_wave_cdn = util.get_cdn_image(str(game["ending_wave"]), "Wave")
            temp_dict = {"EndWave": end_wave_cdn, "Result_String": "", "Version": game["version"], "EloChange": ""
                         ,"Date": game["date"], "gamelink": f"/gameviewer/{game["game_id"]}",
                         "time_ago": util.time_ago(game["date"]), "players_data": [], "Opener": "", "Mastermind": "",
                         "Spell": "", "Worker": "", "Megamind": False, "MVP": False}
            for player in game["players_data"]:
                temp_dict["players_data"].append([player["player_name"], player["player_elo"], player["party_size"]])
                if player["player_id"] == playerid:
                    # Players
                    teammate = game["players_data"][player_map[player["player_slot"]][0]]
                    enemy1 = game["players_data"][player_map[player["player_slot"]][1]]
                    enemy2 = game["players_data"][player_map[player["player_slot"]][2]]
                    if player["mvp_score"] > teammate["mvp_score"]:
                        temp_dict["MVP"] = True
                        mvp_count += 1
                    for p in [[teammate, "Teammates"],[enemy1, "Enemies"],[enemy2, "Enemies"]]:
                        if p[0]["player_id"] in player_dict[p[1]]:
                            player_dict[p[1]][p[0]["player_id"]]["Count"] += 1
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
        try:
            mvp_rate = round(mvp_count / games * 100, 1)
        except ZeroDivisionError:
            mvp_rate = 0
        return render_template(
            "profile.html",
            api_profile=api_profile, api_stats=api_stats, get_rank_url=util.get_rank_url, winrate=util.custom_winrate,
            stats_list=stats_list, image_list=image_list, playername=playername, history=history_parsed, short_history = short_history,
            winlose=winlose, elochange=util.plus_prefix(elochange), playerurl = f"/profile/{playername}/", values=values,
            labels=labels, games=games, wave1 = wave1_percents, mms = mms, openers = openers, get_cdn = util.get_cdn_image, elo=elo,
            patch = patch, spells = spells, player_dict=player_dict, profile=True, plus_prefix=util.plus_prefix, patch_list = patches2,
            player_rank=player_rank, refresh_in_progress=in_progress, cooldown_duration=cooldown_duration, playerid=playerid, mvp_rate=mvp_rate)
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
        
        if stats not in website_stats:
            return render_template("no_data.html", text="Page not found.")
        raw_data = None
        # get player profile
        result = get_player_profile(playername)
        if not result:
            return render_template("no_data.html", text=f"{playername} not found.")
        playerid = result["playerid"]
        api_profile = result["api_profile"]
        playername2 = api_profile["playerName"]
        #GET GAMES JSON
        path = f"Files/player_cache/{playername2}_{patch}_{elo}.msgpack"
        history_raw = None
        if os.path.isfile(path):
            mod_date = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)
            date_diff = datetime.now(tz=timezone.utc) - mod_date
            minutes_diff = date_diff.total_seconds() / 60
            if minutes_diff > 30:
                os.remove(path)
            else:
                with open(path, "rb") as f:
                    history_raw = msgpack.unpackb(f.read(), raw=False)
        if not history_raw:
            req_columns = [[GameData.game_id, GameData.queue, GameData.date, GameData.version, GameData.ending_wave, GameData.game_elo, GameData.player_ids, GameData.spell_choices, GameData.game_length,
                            PlayerData.player_id, PlayerData.player_slot, PlayerData.game_result, PlayerData.player_elo, PlayerData.legion, PlayerData.opener, PlayerData.spell,
                            PlayerData.workers_per_wave, PlayerData.megamind, PlayerData.build_per_wave, PlayerData.champ_location, PlayerData.spell_location, PlayerData.fighters,
                            PlayerData.mercs_sent_per_wave, PlayerData.leaks_per_wave, PlayerData.kingups_sent_per_wave, PlayerData.fighter_value_per_wave, PlayerData.income_per_wave],
                           ["game_id", "queue", "date", "version", "ending_wave", "game_elo", "spell_choices", "game_length"],
                           ["player_id", "player_slot", "game_result", "player_elo", "legion", "opener", "spell", "workers_per_wave", "megamind", "build_per_wave",
                            "champ_location", "spell_location", "fighters", "mercs_sent_per_wave", "leaks_per_wave", "kingups_sent_per_wave", "fighter_value_per_wave",
                            "income_per_wave"]]
            history_raw = drachbot_db.get_matchistory(playerid, 0, elo, patch, earlier_than_wave10=True, req_columns=req_columns, pname=playername, skip_stats=True)
            with open(path, "wb") as f:
                f.write(msgpack.packb(history_raw, default=str))
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
                    sub_headers = [["Champions", "Targets", "rollstats"], ["Openers", "Opener", "openstats"], ["Spells", "Spell", "spellstats"], ["Rolls", "Rolls", "rollstats"]]
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
                raw_data = drachbot.openstats.openstats(playerid, 0, elo, patch, data_only=True, history_raw=history_raw)
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
                    sub_headers = [["Best Send", "Mercs", "mercstats"], ["Best Unit", "Units", "unitstats"]]
                else:
                    header_keys = ["Games", "Winrate", "Playrate"]
                    sub_headers = [["Sends", "Mercs", "mercstats"], ["Units", "Units", "unitstats"]]
                raw_data = drachbot.wavestats.wavestats(playerid, 0, elo, patch, history_raw=history_raw)
                games = raw_data[1]
                avg_elo = raw_data[2]
                raw_data = raw_data[0]
            case "gamestats":
                title = f"{playername2}'s Game"
                title_image = "https://cdn.legiontd2.com/icons/DefaultAvatar.png"
                header_title = "Game"
                raw_data = drachbot.gamestats.gamestats(playerid=playerid, history_raw=history_raw)
                if type(raw_data) == str:
                    return render_template("no_data.html", text="No Data")
                games = raw_data[3]
                avg_elo = raw_data[4]
                raw_data = {"Wave1Stats": raw_data[1], "GameLength": raw_data[2], "WaveDict": raw_data[0]}
        if type(raw_data) == str:
            return render_template("no_data.html", text="No Data")
        if raw_data:
            if stats != "mmstats" and stats != "megamindstats" and stats != "gamestats":
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
        elos = [2800, 2600, 2400, 2200, 2000, 1800, 1600, 1400, 1200, 1000, 0]
        if stats == "gamestats":
            return render_template("gamestats.html", data=raw_data, elo_brackets=elos, custom_winrate=util.custom_winrate,
                                   games=games, avg_elo=avg_elo, patch=patch, patch_list=patches, elo=elo, custom_divide=util.custom_divide,
                                   human_format=util.human_format, get_perf_list=util.get_perf_list, get_dict_value=util.get_dict_value,
                                   specific_key=specific_key, get_unit_name=util.get_unit_name, sort_dict=util.sort_dict, get_gamestats_values=util.get_gamestats_values,
                                   stats=stats, get_key_value=util.get_key_value, get_cdn_image=util.get_cdn_image, mm_list=mm_list, get_tooltip=util.get_tooltip,
                                   get_rank_url=util.get_rank_url, get_avg_end_wave=util.get_avg_end_wave,playerurl=f"/profile/{playername}/", playername2=playername2, patch_selector=True,
                                   title=title, title_image=title_image, header_title=header_title)
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
    if stats not in website_stats:
        return render_template("no_data.html", text="Page not found.")
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
                sub_headers = [["Champions", "Targets", "rollstats"],["Openers", "Opener", "openstats"], ["Spells", "Spell", "spellstats"], ["Rolls", "Rolls", "rollstats"]]
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
                sub_headers = [["Best Send", "Mercs", "mercstats"], ["Best Unit", "Units", "unitstats"]]
            else:
                header_keys = ["Games", "Winrate", "Playrate"]
                sub_headers = [["Sends", "Mercs", "mercstats"], ["Units", "Units", "unitstats"]]
            folder = "wavestats"
        case "gamestats":
            title = "Game"
            title_image = "https://cdn.legiontd2.com/icons/DefaultAvatar.png"
            header_title = "Game"
            folder = "gamestats"
    for file in os.listdir(shared_folder+f"data/{folder}/"):
        if file.startswith(f"{patch}_{elo}"):
            games = file.split("_")[2]
            try:
                games = int(games)
            except Exception:
                return render_template("no_data.html", text="No Data")
            avg_elo = file.split("_")[3].replace(".json", "")
            with open(shared_folder+f"data/{folder}/"+file, "r") as f:
                mod_date = util.time_ago(datetime.fromtimestamp(os.path.getmtime(shared_folder+f"data/{folder}/"+file)).timestamp())
                raw_data = json.load(f)
                f.close()
    if raw_data:
        if stats != "mmstats" and stats != "gamestats":
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
    if stats == "gamestats":
        return render_template("gamestats.html", data=raw_data, elo_brackets=elos, custom_winrate=util.custom_winrate,
                               games=games, avg_elo=avg_elo, patch=patch, patch_list=patches, elo=elo, custom_divide=util.custom_divide,
                               human_format=util.human_format, get_perf_list=util.get_perf_list, get_dict_value=util.get_dict_value,
                               specific_key=specific_key, get_unit_name=util.get_unit_name, sort_dict=util.sort_dict, get_gamestats_values =util.get_gamestats_values,
                               stats=stats, get_key_value=util.get_key_value, get_cdn_image=util.get_cdn_image, mm_list=mm_list,
                               mod_date=mod_date, get_tooltip=util.get_tooltip, get_rank_url=util.get_rank_url, get_avg_end_wave=util.get_avg_end_wave,
                               playerurl="", playername2=playername2, patch_selector=False, title=title, title_image=title_image, header_title=header_title)
    elif specific_key == "All":
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
    for file in os.listdir("Files/player_cache"):
        os.remove(f"Files/player_cache/{file}")
    app.run(host="0.0.0.0", debug=True)
else:
    from waitress import serve
    scheduler.add_job(id = 'Scheduled Task', func=leaderboard_task, trigger="interval", seconds=180)
    scheduler.start()
    for file in os.listdir("Files/player_cache"):
        os.remove(f"Files/player_cache/{file}")
    serve(app, host="0.0.0.0", port=54937, threads=50)