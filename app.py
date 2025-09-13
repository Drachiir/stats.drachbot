import os
import platform
import json
import sqlite3
import traceback
from datetime import datetime, timezone, timedelta
import requests
from flask_caching import Cache
from flask import Flask, render_template, redirect, url_for, send_from_directory, request, session, jsonify, abort
import re
import drachbot.legion_api as legion_api
import drachbot.drachbot_db as drachbot_db
import drachbot.mmstats
import drachbot.openstats
import drachbot.spellstats
import drachbot.unitstats
import drachbot.wavestats
import drachbot.gamestats
import drachbot.matchupstats
import drachbot.sendstats
import util
from drachbot.peewee_pg import GameData, PlayerData, close_db, get_db
from util import get_rank_url, custom_winrate, plus_prefix, custom_divide, get_gamestats_values, human_format, clean_unit_name
from flask_apscheduler import APScheduler
from playfab_api import *
from flask_cors import CORS, cross_origin
import threading
from threading import Thread
import msgpack
import sitedb

with open('Files/json/Secrets.json', 'r') as f:
    secret_file = json.load(f)
    f.close()

sitedb.init_db()
cache = Cache()
app = Flask(__name__)
app.secret_key = secret_file["flask_secret_key"]
CORS(app, resources={r"/api/*": {"origins": "*"}})
scheduler = APScheduler()

@app.teardown_request
def teardown_request(exception):
    """Ensure the database connection is closed if used."""
    close_db(exception)

def get_player_profile(playername):
    playerid = playername if re.fullmatch(r'(?=.*[0-9])(?=.*[A-F])[0-9A-F]{13,16}', playername) else None
    api_profile = legion_api.getprofile(playerid or playername, by_id=bool(playerid))
    if api_profile in [0, 1]:
        playfab_profile = get_profile_from_playfab(playername)
        if playfab_profile:
            playerid = playfab_profile["AccountInfo"]["PlayFabId"]
            api_profile = {"playerName": playfab_profile["AccountInfo"]["TitleInfo"]["DisplayName"],
                           "avatarUrl": playfab_profile["AccountInfo"]["TitleInfo"]["AvatarUrl"]}
        else:
            playerid = drachbot_db.get_playerid(playername) if not playerid else None
            api_profile = {"playerName": playername, "avatarUrl": "icons/DefaultAvatar.png"}
        if not playerid:
            return None
    else:
        playerid = api_profile["_id"]
    api_profile["guildTag"] = ""
    return {"playerid": playerid, "api_profile": api_profile}

def validate_custom_patch(patch:str):
    patch = patch.strip()
    if not re.fullmatch(r'v\d+\.\d+\.\d+', patch):
        return False
    return True

def main_leaderboard_task():
    leaderboard_task(1)
    with open("leaderboard_temp.json", "r") as f:
        temp_data = json.load(f)

    # for player in temp_data["Leaderboard"]:
    #     playerid = player["PlayFabId"]
    #     req_columns = [
    #         [GameData.queue, GameData.date, GameData.ending_wave, GameData.game_elo, GameData.player_ids,
    #          PlayerData.player_id, PlayerData.game_result, PlayerData.legion, PlayerData.megamind, PlayerData.opener],
    #         ["date", "ending_wave", "game_elo"],
    #         ["player_id", "game_result", "legion", "megamind", "opener"]
    #     ]
    #     history: list = drachbot_db.get_matchistory(playerid, 50, earlier_than_wave10=True, req_columns=req_columns, skip_stats=True, sort_players=False)
    #     mms = {}
    #     openers_data = {}
    #     win_streak = 0
    #     lose_streak = 0
    #     history.reverse()
    #     for game in history:
    #         for player2 in game["players_data"]:
    #             if player2["player_id"] != playerid:
    #                 continue
    #             if player2["megamind"]:
    #                 player2["legion"] = "Megamind"
    #             # Count Masterminds
    #             mms[player2["legion"]] = mms.get(player2["legion"], 0) + 1
    #             # Count Openers
    #             for opener_unit in set(player2["opener"].split(",")):
    #                 openers_data[opener_unit] = openers_data.get(opener_unit, 0) + 1
    #             # Win/Lose streak tracking
    #             if player2["game_result"] == "won":
    #                 win_streak += 1
    #                 lose_streak = 0
    #             else:
    #                 lose_streak += 1
    #                 win_streak = 0
    #     top_mms = dict(sorted(mms.items(), key=lambda x: x[1], reverse=True)[:3])
    #     top_openers = dict(sorted(openers_data.items(), key=lambda x: x[1], reverse=True)[:3])
    #     drachbot_data = {
    #         "Masterminds": top_mms,
    #         "WinStreak": win_streak,
    #         "LoseStreak": lose_streak,
    #         "Openers": top_openers
    #     }
    #     player["DrachbotData"] = drachbot_data
    with open("leaderboard.json", "w") as f:
        json.dump(temp_data, f)
    
    # Also fetch event leaderboard
    event_leaderboard_task(1)
    try:
        with open("event_leaderboard_temp.json", "r") as f:
            event_temp_data = json.load(f)
        with open("event_leaderboard.json", "w") as f:
            json.dump(event_temp_data, f)
    except FileNotFoundError:
        print("Event leaderboard temp file not found")

def run_leaderboard_task_in_thread():
    thread = threading.Thread(target=main_leaderboard_task, daemon=True)
    thread.start()

if platform.system() == "Linux":
    timeout = 600
    timeout2 = 300
else:
    timeout = 1
    timeout2 = 1
    
app.config['CACHE_TYPE'] = 'simple'
app.config['CACHE_DEFAULT_TIMEOUT'] = timeout
app.config['CACHE_THRESHOLD'] = 5000
app.config['CACHE_KEY_PREFIX'] = 'myapp_'
cache.init_app(app)

@app.before_request
def block_bad_bots():
    bad_bots = ["BadBot", "Scrapy", "Python-urllib", "curl"]
    user_agent = request.headers.get('User-Agent', '').lower()
    if any(bot.lower() in user_agent for bot in bad_bots):
        abort(403)  # Forbidden

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

@app.errorhandler(404)
def not_found_error(error):
    return render_template('no_data.html', text="Page not found"), 404

if platform.system() == "Linux":
    shared_folder_live = "/shared/livegames"
    shared_folder = "/shared2/"
else:
    shared_folder = "D:/Projekte/Python/Drachbot/shared2/"
    shared_folder_live = "shared/livegames"

with open("defaults.json", "r") as f:
    defaults_json = json.load(f)
    f.close()

DISCORD_CLIENT_ID = secret_file["discord_id"]
DISCORD_CLIENT_SECRET = secret_file["discord_secret"]
DISCORD_REDIRECT_URI = secret_file["discord_uri"]

DISCORD_API_BASE = "https://discord.com/api"
OAUTH_AUTHORIZE_URL = f"{DISCORD_API_BASE}/oauth2/authorize"
OAUTH_TOKEN_URL = f"{DISCORD_API_BASE}/oauth2/token"
USER_API_URL = f"{DISCORD_API_BASE}/users/@me"

defaults = defaults_json["Defaults"]
defaults2 = defaults_json["Defaults2"]
mm_list = defaults_json["MMs"]
elos = defaults_json["Elos"]
elos2 = defaults_json["Elos2"]
patches = defaults_json["Patches"]
buff_spells = defaults_json["BuffSpells"]
website_stats = defaults_json["StatCategories"]

@app.route("/login/")
def login():
    next_url = request.args.get("next") or url_for("home")
    session["next_url"] = next_url
    return redirect(
        f"{OAUTH_AUTHORIZE_URL}?client_id={DISCORD_CLIENT_ID}"
        f"&redirect_uri={DISCORD_REDIRECT_URI}"
        f"&response_type=code&scope=identify"
    )

@app.route("/callback")
def callback():
    code = request.args.get("code")
    data = {
        "client_id": DISCORD_CLIENT_ID,
        "client_secret": DISCORD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": DISCORD_REDIRECT_URI,
        "scope": "identify"
    }

    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    token_response = requests.post(OAUTH_TOKEN_URL, data=data, headers=headers)
    token_response.raise_for_status()
    access_token = token_response.json().get("access_token")

    user_response = requests.get(USER_API_URL, headers={"Authorization": f"Bearer {access_token}"})
    user_response.raise_for_status()
    user_data = user_response.json()

    # Fetch player_id from external API
    player_id = sitedb.get_player_id(user_data["id"])
    
    # Fetch LTD2 profile data if player_id exists
    ltd2_playername = None
    ltd2_avatar_url = None
    if player_id:
        try:
            get_db()
            ltd2_profile = drachbot_db.get_player_profile(player_id, by_id=True)
            if ltd2_profile:
                ltd2_playername = ltd2_profile["api_profile"]["playerName"]
                ltd2_avatar_url = ltd2_profile["api_profile"]["avatarUrl"]
        except Exception as e:
            print(f"Error fetching LTD2 profile: {e}")

    # Store in your local DB
    sitedb.save_user_to_db(user_data, player_id, ltd2_playername, ltd2_avatar_url)

    # Save only what's needed in session
    session["user"] = {
        "id": user_data["id"],
        "username": user_data["username"],
        "discriminator": user_data["discriminator"],
        "avatar": user_data["avatar"],
        "player_id": player_id,
        "ltd2_playername": ltd2_playername,
        "ltd2_avatar_url": ltd2_avatar_url
    }
    session.permanent = True
    next_url = session.pop("next_url", url_for("home"))
    return redirect(next_url)

@app.route("/logout/")
def logout():
    session.clear()
    return redirect(request.referrer or url_for("home"))

@app.context_processor
def inject_user():
    user = session.get("user")
    user_preferences = {}
    if user:
        # Get LTD2 data from database if not in session
        if not user.get("ltd2_playername") and user.get("player_id"):
            ltd2_data = sitedb.get_user_ltd2_data(user["id"])
            user.update(ltd2_data)
        # Get user preferences for all pages
        user_preferences = sitedb.get_user_preferences(user["id"])
    return dict(user=user, discord_login=True, user_preferences=user_preferences)

@app.route("/api/defaults")
def api_defaults():
    return defaults_json

@app.route("/api/user/preferences", methods=['GET'])
def get_user_preferences_api():
    user = session.get("user")
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    
    preferences = sitedb.get_user_preferences(user["id"])
    return jsonify(preferences)

@app.route("/api/user/preferences", methods=['POST'])
def update_user_preferences_api():
    user = session.get("user")
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    # Validate and sanitize Twitch username
    if "twitch_username" in data:
        twitch_username = data["twitch_username"]
        if twitch_username:
            # Remove any whitespace and convert to lowercase
            twitch_username = twitch_username.strip().lower()
            # Validate Twitch username format (alphanumeric, underscores, hyphens only)
            if not re.match(r'^[a-z0-9_]+$', twitch_username):
                return jsonify({"error": "Invalid Twitch username format"}), 400
            # Limit length (Twitch usernames are max 25 characters)
            if len(twitch_username) > 25:
                return jsonify({"error": "Twitch username too long"}), 400
            data["twitch_username"] = twitch_username
    
    # Validate and sanitize YouTube username
    if "youtube_username" in data:
        youtube_username = data["youtube_username"]
        if youtube_username:
            # Remove any whitespace and convert to lowercase
            youtube_username = youtube_username.strip().lower()
            # Validate YouTube username format (alphanumeric, underscores only)
            if not re.match(r'^[a-z0-9_]+$', youtube_username):
                return jsonify({"error": "Invalid YouTube username format"}), 400
            # Limit length (YouTube usernames are max 30 characters)
            if len(youtube_username) > 30:
                return jsonify({"error": "YouTube username too long"}), 400
            data["youtube_username"] = youtube_username
    
    sitedb.update_user_preferences(user["id"], data)
    return jsonify({"message": "Preferences updated successfully"})

@app.route("/api/user/refresh-ltd2-account", methods=['POST'])
def refresh_ltd2_account_api():
    user = session.get("user")
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    
    # Get fresh player_id from external API
    player_id = sitedb.get_player_id(user["id"])
    
    # Update the user's data in the database
    conn = sqlite3.connect("site.db")
    cursor = conn.cursor()
    
    if player_id:
        # Fetch LTD2 profile data
        ltd2_playername = None
        ltd2_avatar_url = None
        try:
            get_db()
            ltd2_profile = drachbot_db.get_player_profile(player_id, by_id=True)
            if ltd2_profile:
                ltd2_playername = ltd2_profile["api_profile"]["playerName"]
                ltd2_avatar_url = ltd2_profile["api_profile"]["avatarUrl"]
        except Exception as e:
            print(f"Error fetching LTD2 profile: {e}")
        
        # Update with linked account data
        cursor.execute("UPDATE users SET player_id = ?, ltd2_playername = ?, ltd2_avatar_url = ? WHERE discord_id = ?", 
                      (player_id, ltd2_playername, ltd2_avatar_url, user["id"]))
        
        # Update session
        session["user"]["player_id"] = player_id
        session["user"]["ltd2_playername"] = ltd2_playername
        session["user"]["ltd2_avatar_url"] = ltd2_avatar_url
        
        message = "LTD2 account link found: " + ltd2_playername
    else:
        # Clear linked account data (account was unlinked)
        cursor.execute("UPDATE users SET player_id = NULL, ltd2_playername = NULL, ltd2_avatar_url = NULL WHERE discord_id = ?", 
                      (user["id"],))
        
        # Update session
        session["user"]["player_id"] = None
        session["user"]["ltd2_playername"] = None
        session["user"]["ltd2_avatar_url"] = None
        
        message = "No LTD2 account linked"
    
    conn.commit()
    conn.close()
    
    return jsonify({"message": message, "player_id": player_id})

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
    avg_elo = None
    with open("leaderboard.json", "r") as f:
        leaderboard_data = json.load(f)
    for i, folder in enumerate(folder_list):
        temp_data = {}
        total_games = 0
        for file in os.listdir(shared_folder + f"data/{folder}/"):
            file_name_split = file.split("_")
            file_patch = file_name_split[0]

            try:
                file_elo = int(file_name_split[1])
                file_games = int(file_name_split[2])
            except ValueError:
                continue

            file_avg_elo = file_name_split[3].replace(".msgpack", "")

            if file_patch == defaults[0] and file_elo >= defaults[1]:
                total_games += file_games
                avg_elo = file_avg_elo

                with open(shared_folder + f"data/{folder}/" + file, "rb") as f:
                    raw_data = msgpack.unpackb(f.read(), raw=False)
                    raw_data = {key: value for key, value in raw_data.items() if value["Count"] != 0}
                    temp_data = util.merge_dicts(temp_data, raw_data)

        if temp_data:
            # if folder == "wavestats":
            #     sorted_keys = sorted(temp_data, key=lambda x: temp_data[x]['EndCount'], reverse=True)
            #     temp_data = {k: temp_data[k] for k in sorted_keys}
            # else:
            #     sorted_keys = sorted(temp_data, key=lambda x: temp_data[x]['Count'], reverse=True)
            #     temp_data = {k: temp_data[k] for k in sorted_keys}

            temp_keys = list(temp_data.keys())
            keys.append([folder, temp_keys])
            data_list.append([folder, total_games, avg_elo, temp_data, header_list[i], title_list[i], temp_keys[:2]])
    try:
        total_games = util.human_format(int(data_list[0][1]))
    except IndexError:
        total_games = "0"
    return render_template("home.html", data_list=data_list, image_list=image_list, keys=keys,
                           elo=defaults[1], patch=defaults[0], get_cdn_image = util.get_cdn_image, get_key_value=util.get_key_value,
                           total_games=total_games, get_tooltip = util.get_tooltip, home=True, leaderboard_data_home = leaderboard_data,
                           get_value=util.get_value_playfab, winrate = util.custom_winrate, get_rank_url=util.get_rank_url)

@app.route('/classicmodes')
@cache.cached(timeout=10)
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
        for i in range(22)
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
        get_db()
        stats = get_player_profile(playername)
        if not stats:
            return render_template("no_data.html", text=f"Player { playername } not found.")
        player_id = stats["playerid"]
        api_profile = stats["api_profile"]
        leaderboard_data = get_playfab_stats(player_id, 100)
    if not leaderboard_data:
        return render_template("no_data.html", text=f"Error loading leaderboard, try again later.")
    return render_template("leaderboard.html", leaderboard = leaderboard_data, get_rank_url=util.get_rank_url, get_value=util.get_value_playfab,
                           winrate = util.custom_winrate, api_profile=api_profile, leaderboard_page = True, get_cdn = util.get_cdn_image)

@app.route("/event-leaderboard", defaults={"playername": None})
@app.route("/event-leaderboard/<playername>")
def event_leaderboard(playername):
    if not playername:
        api_profile = None
        try:
            with open("event_leaderboard.json", "r") as f:
                leaderboard_data = json.load(f)
        except FileNotFoundError:
            return render_template("no_data.html", text=f"Event leaderboard not available yet, try again later.")
    else:
        get_db()
        stats = get_player_profile(playername)
        if not stats:
            return render_template("no_data.html", text=f"Player { playername } not found.")
        player_id = stats["playerid"]
        api_profile = stats["api_profile"]
        leaderboard_data = get_playfab_event_stats(player_id, 100)
    if not leaderboard_data:
        return render_template("no_data.html", text=f"Error loading event leaderboard, try again later.")
    return render_template("event_leaderboard.html", leaderboard = leaderboard_data, get_rank_url=util.get_rank_url, get_value=util.get_value_playfab,
                           winrate = util.custom_winrate, api_profile=api_profile, event_leaderboard_page = True, get_cdn = util.get_cdn_image)

@app.route("/rank-distribution/", methods=['GET'], defaults={'snapshot': None})
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
    snapshots_list = []
    for ss in os.listdir(f"{shared_folder}/leaderboard"):
        if not ss.endswith(".json"):
            continue
        snapshots_list.append(ss.split("_")[2].replace(".json", ""))
    snapshots_list = sorted(snapshots_list, key=lambda x: int(x.split("-")[2]+x.split("-")[1]+x.split("-")[0]), reverse=True)
    snapshot = snapshot if snapshot else snapshots_list[0]
    try:
        with open(f"{shared_folder}/leaderboard/leaderboard_parsed_{snapshot}.json", "r") as f:
            leaderboard_data = json.load(f)
    except FileNotFoundError:
        return render_template("no_data.html", text=f"No data.")
    return render_template("rank-distribution.html", min_games=min_games, leaderboard_data=leaderboard_data, min_winrate=min_winrate,
                           snapshots_list=snapshots_list, snapshot=snapshot)

@app.route('/wave-distribution/', defaults={"elo": defaults[1], "patch": defaults[0]})
@app.route('/wave-distribution/<patch>/', defaults={"elo": defaults[1]})
@app.route('/wave-distribution/<patch>/<elo>/')
def wave_distribution(patch, elo):
    elo = str(elo)
    elo1 = elo
    elo2 = None
    if "-" in elo:
        elo1 = elo.split("-")[0]
        elo2 = elo.split("-")[1]
    games = 0
    folder = "wavestats"
    wave_data = {}
    if patch.startswith("v"):
        if not validate_custom_patch(patch):
            return render_template("no_data.html", text=f"Unsupported query")
        path = f"Files/player_cache/All_{patch}_{elo}.msgpack"
        history_raw = None
        if os.path.isfile(path):
            mod_date2 = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)
            date_diff = datetime.now(tz=timezone.utc) - mod_date2
            minutes_diff = date_diff.total_seconds() / 60
            if minutes_diff > 120:
                os.remove(path)
            else:
                with open(path, "rb") as f:
                    history_raw = msgpack.unpackb(f.read(), raw=False)
        if not history_raw:
            get_db()
            req_columns = [[GameData.game_id, GameData.queue, GameData.date, GameData.version, GameData.ending_wave, GameData.game_elo, GameData.player_ids, GameData.spell_choices, GameData.game_length,
                            PlayerData.player_id, PlayerData.player_slot, PlayerData.game_result, PlayerData.player_elo, PlayerData.legion, PlayerData.opener, PlayerData.spell,
                            PlayerData.workers_per_wave, PlayerData.megamind, PlayerData.build_per_wave, PlayerData.champ_location, PlayerData.spell_location, PlayerData.fighters,
                            PlayerData.mercs_sent_per_wave, PlayerData.leaks_per_wave, PlayerData.kingups_sent_per_wave, PlayerData.fighter_value_per_wave, PlayerData.income_per_wave],
                           ["game_id", "queue", "date", "version", "ending_wave", "game_elo", "spell_choices", "game_length"],
                           ["player_id", "player_slot", "game_result", "player_elo", "legion", "opener", "spell", "workers_per_wave", "megamind", "build_per_wave",
                            "champ_location", "spell_location", "fighters", "mercs_sent_per_wave", "leaks_per_wave", "kingups_sent_per_wave", "fighter_value_per_wave",
                            "income_per_wave"]]
            history_raw = drachbot_db.get_matchistory("all", 0, int(elo1), patch[1:], earlier_than_wave10=True, req_columns=req_columns)
            if len(history_raw) == 0:
                return render_template("no_data.html", text=f"No Data for {patch}")
            with open(path, "wb") as f:
                f.write(msgpack.packb(history_raw, default=str))
        raw_data = drachbot.wavestats.wavestats("all", 0, int(elo), patch[1:], history_raw=history_raw)
        games = raw_data[1]
        avg_elo = raw_data[2]
        wave_data = raw_data[0]
    else:
        if elo1 and elo2:
            for file in os.listdir(shared_folder + f"data/{folder}/"):
                if file.startswith(f"{patch}_{elo1}"):
                    games = file.split("_")[2]
                    try:
                        games = int(games)
                    except Exception:
                        return render_template("no_data.html", text="No Data")
                    avg_elo = file.split("_")[3].replace(".msgpack", "")
                    with open(shared_folder + f"data/{folder}/" + file, "rb") as f:
                        wave_data = msgpack.unpackb(f.read(), raw=False)
        else:
            for file in os.listdir(shared_folder + f"data/{folder}/"):
                file_name_split = file.split("_")
                file_patch = file_name_split[0]
                try:
                    file_elo = int(file_name_split[1])
                    file_games = int(file_name_split[2])
                except ValueError:
                    continue

                file_avg_elo = file_name_split[3].replace(".msgpack", "")

                if file_patch == patch and file_elo >= int(elo):
                    games += file_games
                    with open(shared_folder + f"data/{folder}/" + file, "rb") as f:
                        temp_data = msgpack.unpackb(f.read(), raw=False)
                        wave_data = util.merge_dicts(wave_data, temp_data)
            avg_elo = f"{elo}+"
    if not wave_data:
        return render_template("no_data.html", text=f"No data.")
    return render_template("wave-distribution.html", wave_data=wave_data, patch=patch, elo= elo, games= games,
                           avg_elo=avg_elo, patch_list=patches, elos=elos2, get_rank_url=util.get_rank_url, get_avg_end_wave=util.get_avg_end_wave,
                           human_format=util.human_format)

@app.route('/proleaks/', defaults= {"wave": 1, "patch": defaults[0]})
@app.route('/proleaks/<wave>', defaults= {"patch": defaults[0]})
@app.route('/proleaks/<wave>/<patch>')
@cache.cached(timeout=timeout)
def proleaks(wave, patch):
    for datajson in os.listdir(f"{shared_folder}/data/proleaks/"):
        if datajson.split("_")[0] == patch:
            games = datajson.split("_")[2]
            try:
                games = int(games)
            except Exception:
                return render_template("no_data.html", text="No Data")
            avg_elo = datajson.split("_")[3].replace(".json", "")
            mod_date = util.time_ago(datetime.fromtimestamp(os.path.getmtime(f"{shared_folder}/data/proleaks/{datajson}")).timestamp())
            with open(f"{shared_folder}/data/proleaks/{datajson}", "rb") as f:
                data = msgpack.unpackb(f.read(), raw=False)
            break
    else:
        return render_template("no_data.html", text=f"No data.")
    if f"Wave{wave}" not in data:
        return render_template("no_data.html", text=f"No data.")
    return render_template("proleaks.html", proleak_data = data[f"Wave{wave}"], wave=wave, get_cdn=util.get_cdn_image, get_rank_url=util.get_rank_url,
                           const_file = util.const_file, plus_prefix = util.plus_prefix, games=games, avg_elo=avg_elo, patch_name = patch, human_format = util.human_format,
                           clean_unit_name = util.clean_unit_name, patch_list = patches, wave_string = f"Wave{wave}", mod_date=mod_date)

@app.route('/openers/', defaults= {"opener": None, "patch": defaults[0]})
@app.route('/openers/<patch>', defaults= {"opener": None})
@app.route('/openers/<patch>/<opener>')
@cache.cached(timeout=timeout)
def openers(patch, opener):
    for datajson in os.listdir(f"{shared_folder}/data/openers/"):
        if datajson.startswith(f"{patch}"):
            games = datajson.split("_")[2]
            try:
                games = int(games)
            except Exception:
                return render_template("no_data.html", text="No Data")
            avg_elo = datajson.split("_")[3].replace(".msgpack", "")
            mod_date = util.time_ago(datetime.fromtimestamp(os.path.getmtime(f"{shared_folder}/data/openers/{datajson}")).timestamp())
            with open(f"{shared_folder}/data/openers/{datajson}", "rb") as f:
                data = msgpack.unpackb(f.read(), raw=False)
            break
    else:
        return render_template("no_data.html", text=f"No data.")
    new_patches = patches[:]
    if not opener:
        return render_template("openers_overview.html", openers_data=data, get_cdn=util.get_cdn_image, get_rank_url=util.get_rank_url,
                               const_file=util.const_file, plus_prefix=util.plus_prefix, games=games, avg_elo=avg_elo, patch_name=patch, human_format=util.human_format,
                               clean_unit_name=util.clean_unit_name, patch_list=new_patches, mod_date=mod_date, opener_name = True)
    else:
        if opener not in data:
            return render_template("no_data.html", text=f"Opener not found.")
        return render_template("openers.html", openers_data = data[opener]["Data"], get_cdn=util.get_cdn_image, get_rank_url=util.get_rank_url,
                               const_file = util.const_file, plus_prefix = util.plus_prefix, games=data[opener]["Count"], avg_elo=avg_elo, patch_name = patch, human_format = util.human_format,
                               clean_unit_name = util.clean_unit_name, patch_list = new_patches, mod_date=mod_date, opener_name = opener)


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

@app.route("/api/get_player_profile/<playername>")
def get_player_profile_api(playername):
    get_db()
    drachbot_profile = drachbot_db.get_player_profile(playername)
    if drachbot_profile:
        playerid = drachbot_profile["playerid"]
        api_profile = drachbot_profile["api_profile"]
        country = drachbot_profile["country"]
        player_rank = api_profile["rank"]
    else:
        result = get_player_profile(playername)
        if not result:
            return jsonify({"error": "Not Found"}), 400
        playerid = result["playerid"]
        api_profile = result["api_profile"]
        country = ""
        player_rank = 0
        api_profile["elo"] = ""
        api_profile["rank"] = ""
    return {"playerid": playerid, "api_profile": api_profile, "country": country, "rank": player_rank}

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
    get_db()
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
        [GameData.queue, GameData.date, GameData.ending_wave, GameData.game_elo, GameData.player_ids,
         PlayerData.player_id, PlayerData.game_result, PlayerData.elo_change, PlayerData.legion,
         PlayerData.mercs_sent_per_wave, PlayerData.kingups_sent_per_wave, PlayerData.megamind],
        ["date", "ending_wave", "game_elo"],
        ["player_id", "game_result", "elo_change", "legion", "mercs_sent_per_wave", "kingups_sent_per_wave", "megamind"]]
    history = drachbot_db.get_matchistory(playerid, 20, earlier_than_wave10=True, req_columns=req_columns, skip_stats=True, sort_players=False)
    # if not history:
    #     history = drachbot_db.get_matchistory(playerid, 20, earlier_than_wave10=True, req_columns=req_columns, skip_stats=True, get_new_games=True)
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

@app.route("/api/request_games/<playername>", defaults={"limit": 1})
@app.route("/api/request_games/<playername>/<limit>")
def request_games_api(playername, limit):
    limit = int(limit)
    limit = 5 if limit > 5 else limit
    if len(playername) > 13 and re.fullmatch(r'(?=.*[0-9])(?=.*[A-F])[0-9A-F]{13,16}', playername):
        playerid = playername
    else:
        get_db()
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
    get_db()
    return jsonify(drachbot_db.get_search_results(search_term)), 200

@app.route('/api/get_player_stats/<playername>', methods=['GET'])
def get_player_stats(playername):
    get_db()
    playerid = drachbot_db.get_playerid(playername)
    if not playerid:
        api_profile = legion_api.getprofile(playername)
        if api_profile in [0, 1]:
            return jsonify({"Status": "Not Found"}), 400
        else:
            playerid = api_profile["_id"]
    api_stats = legion_api.getstats(playerid)
    return api_stats

@app.route('/api/get_simple_history/<playername>', methods=['GET'])
def get_simple_history(playername):
    get_db()
    playerid = drachbot_db.get_playerid(playername)
    if not playerid:
        api_profile = legion_api.getprofile(playername)
        if api_profile in [0, 1]:
            return jsonify({"Status": "Not Found"}), 400
        else:
            playerid = api_profile["_id"]
    req_columns = [
        [GameData.game_id, GameData.queue, GameData.date, GameData.version, GameData.ending_wave, GameData.game_elo, GameData.player_ids, GameData.game_length,
         PlayerData.player_id, PlayerData.player_name, PlayerData.player_elo, PlayerData.player_slot, PlayerData.game_result, PlayerData.elo_change,
         PlayerData.legion],
        ["game_id", "date", "version", "ending_wave", "game_elo", "game_length"],
        ["player_id", "player_name", "player_elo", "player_slot", "game_result", "elo_change", "legion"]]
    history = drachbot_db.get_matchistory(playerid, 10, 0, earlier_than_wave10=True, req_columns=req_columns, skip_stats=True, skip_game_refresh=True)
    return history

@app.route('/api/get_player_matchhistory/<playername>/<playerid>/<patch>/<page>', methods=['GET'])
def get_player_matchhistory(playername, playerid, patch, page):
    path = f"Files/player_cache/{playername}_profile_{patch}.msgpack"
    try:
        with open(path, "rb") as f:
            history = msgpack.unpackb(f.read(), raw=False)
    except FileNotFoundError:
        get_db()
        req_columns = [
            [GameData.game_id, GameData.queue, GameData.date, GameData.version, GameData.ending_wave, GameData.game_elo, GameData.player_ids, GameData.game_length,
             PlayerData.player_id, PlayerData.player_name, PlayerData.player_elo, PlayerData.player_slot, PlayerData.game_result, PlayerData.elo_change,
             PlayerData.legion, PlayerData.mercs_sent_per_wave, PlayerData.kingups_sent_per_wave, PlayerData.opener, PlayerData.megamind, PlayerData.spell,
             PlayerData.workers_per_wave, PlayerData.mvp_score, PlayerData.party_size],
            ["game_id", "date", "version", "ending_wave", "game_elo", "game_length"],
            ["player_id", "player_name", "player_elo", "player_slot", "game_result", "elo_change", "legion",
             "mercs_sent_per_wave", "kingups_sent_per_wave", "opener", "megamind", "spell", "workers_per_wave", "mvp_score", "party_size"]]
        history = drachbot_db.get_matchistory(playerid, 0, 0, patch, earlier_than_wave10=True, req_columns=req_columns, skip_stats=True, include_wave_one_finishes=True)
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
            temp_dict["players_data"].append([player["player_name"], player["player_elo"], player["party_size"], player["player_id"]])
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
                temp_dict["Result_String"] = [player["game_result"], f"Wave {game["ending_wave"]}"]
        history_parsed.append(temp_dict)
    if not history_parsed:
        return "No data found", 404
    return history_parsed

@app.route('/load/<playername>/', defaults={"stats": None,"elo": defaults2[1], "patch": defaults2[0], "specific_key": "All"})
@app.route('/load/<playername>/<stats>/', defaults={"elo": defaults2[1], "patch": defaults2[0], "specific_key": "All"})
@app.route('/load/<playername>/<stats>/<patch>/', defaults={"elo": defaults2[1], "specific_key": "All"})
@app.route('/load/<playername>/<stats>/<patch>/<elo>/', defaults={"specific_key": "All"})
@app.route('/load/<playername>/<stats>/<patch>/<elo>/<specific_key>/')
def load(playername, stats, patch, elo, specific_key):
    get_db()
    session['visited_profile'] = True
    by_id = True if re.fullmatch(r'(?=.*[0-9])(?=.*[A-F])[0-9A-F]{13,16}', playername) else False
    og_data = drachbot_db.get_player_profile(playername, by_id=by_id)
    if og_data:
        playername = og_data["api_profile"]["playerName"]
    if not stats:
        new_patch = request.args.get('patch')
        if new_patch:
            new_patch = f"?patch={new_patch}"
        else:
            new_patch = ""
        return render_template('loading.html', playername=playername, url=f"/profile/{playername}/{new_patch}", og_data=og_data)
    else:
        return render_template('loading.html', playername=playername, url=f"/profile/{playername}/{stats}/{patch}/{elo}/{specific_key}/", og_data=og_data)

@app.route('/profile/<playername>/', defaults={"stats": None,"elo": defaults2[1], "patch": defaults2[0], "specific_key": "All"})
@app.route('/profile/<playername>/<stats>/', defaults={"elo": defaults2[1], "patch": defaults2[0], "specific_key": "All"})
@app.route('/profile/<playername>/<stats>/<patch>/', defaults={"elo": defaults2[1], "specific_key": "All"})
@app.route('/profile/<playername>/<stats>/<patch>/<elo>/', defaults={"specific_key": "All"})
@app.route('/profile/<playername>/<stats>/<patch>/<elo>/<specific_key>/')
def profile(playername, stats, patch, elo, specific_key):
    # Check if profile is private early to avoid expensive operations
    user = session.get("user")
    
    # Get playerid for private check
    if re.fullmatch(r'(?=.*[0-9])(?=.*[A-F])[0-9A-F]{13,16}', playername):
        # playername is already a player ID
        playerid = playername
    else:
        # playername is a name, get the player ID
        get_db()
        playerid = drachbot_db.get_playerid(playername)
    
    # Check if the profile is private
    if playerid:
        is_profile_private = sitedb.is_profile_private(playerid)
        # If profile is private and user is not the owner, show private message
        if is_profile_private and (not user or user.get("player_id") != playerid):
            return render_template('no_data.html', text="User profile is private")
    
    if not stats:
        new_patch = request.args.get('patch')
        if new_patch:
            patch = new_patch.replace("/", "")
            for szn in ["12", "11"]:
                if szn in patch.split(","):
                    patch = szn
                    new_patch = szn
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
        api_stats = {"avatarBorder": "", "flag": "", "Country": ""}
        get_db()
        drachbot_profile = drachbot_db.get_player_profile(playername)
        if drachbot_profile:
            playerid = drachbot_profile["playerid"]
            api_profile = drachbot_profile["api_profile"]
            country = drachbot_profile["country"]
            city = drachbot_profile["city"]
            player_rank = api_profile["rank"]
        else:
            result = get_player_profile(playername)
            if not result:
                return render_template("no_data.html", text=f"{playername} not found.")
            playerid = result["playerid"]
            api_profile = result["api_profile"]
            country = ""
            city = ""
            player_rank = 0
        # Get player stats
        in_progress = player_refresh_state.get(playerid, {}).get('in_progress', False)
        cooldown_duration = get_remaining_cooldown(playerid)
        playfab_stats = get_playfab_stats(playerid)
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
            for stat_key, version in [("rankedWinsThisSeason", 9), ("rankedLossesThisSeason", 9), ("overallElo", 12), ("overallPeakEloThisSeason", 12)]:
                try:
                    api_stats[stat_key] = util.get_value_playfab(player["Profile"]["Statistics"], stat_key, version=version)
                except Exception:
                    api_stats[stat_key] = 0
            try:
                avatar_stacks = int(player["Profile"]["ContactEmailAddresses"][0]["EmailAddress"].split("_")[5].replace("@x.x", "").split("+")[1])
            except Exception:
                avatar_stacks = 0
            api_stats["avatarBorder"] = util.get_avatar_border(avatar_stacks)

            country = player["Profile"]["Locations"][0]["CountryCode"]
            try:
                city = player["Profile"]["Locations"][0]["City"]
            except Exception:
                city = ""
            player_rank = player["Position"] + 1
        else:
            api_stats = legion_api.getstats(playerid)
        try:
            _ = api_stats["rankedWinsThisSeason"]
            _ = api_stats["rankedLossesThisSeason"]
            _ = api_stats["overallElo"]
            _ = api_stats["overallPeakEloThisSeason"]
        except KeyError:
            return render_template("no_data.html", text=f"{playername} not found.")

        api_stats["playerRank"] = player_rank
        api_stats["flag"] = country
        api_stats["city"] = city
        if country:
            countries = util.COUNTRIES_CACHE
            if type(countries["countries"][country]) == list:
                api_stats["Country"] = countries["countries"][country][0]
            else:
                api_stats["Country"] = countries["countries"][country]

        if not api_stats["rankedWinsThisSeason"]:
            api_stats["rankedWinsThisSeason"] = 0
        if not api_stats["rankedLossesThisSeason"]:
            api_stats["rankedLossesThisSeason"] = 0
        stats_list = website_stats
        image_list = [
            "https://cdn.legiontd2.com/icons/Mastermind.png",
            "https://cdn.legiontd2.com/icons/Items/Megamind.png",
            "https://cdn.legiontd2.com/icons/Mastery/5.png",
            "https://cdn.legiontd2.com/icons/Brute.png",
            "https://cdn.legiontd2.com/icons/ChallengerElite.png",
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
            skip_game_refresh = True if api_stats["overallElo"] > 1700 else False
            history = drachbot_db.get_matchistory(playerid, 0, elo, patch, earlier_than_wave10=True, req_columns=req_columns,
                                                  playerstats=api_stats, playerprofile=api_profile, pname=playername, skip_game_refresh=skip_game_refresh, include_wave_one_finishes=True)
            try:
                os.remove(path)
            except Exception:
                pass
            with open(path, "wb") as f:
                f.write(msgpack.packb(history, default=str))
        history_parsed = []
        winlose = {"Overall": [0,0], "SoloQ": [0,0], "DuoQ": [0,0]}
        elochange = {"Overall": 0, "SoloQ": 0, "DuoQ": 0}
        mvp_count = {"Overall": 0, "SoloQ": 0, "DuoQ": 0}
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
        known_names = set()
        for game in history:
            if type(game["date"]) == str:
                game["date"] = datetime.strptime(game["date"], "%Y-%m-%d %H:%M:%S")
            end_wave_cdn = util.get_cdn_image(str(game["ending_wave"]), "Wave")
            temp_dict = {"EndWave": end_wave_cdn, "Result_String": "", "Version": game["version"], "EloChange": ""
                         ,"Date": game["date"], "gamelink": f"/gameviewer/{game["game_id"]}",
                         "time_ago": util.time_ago(game["date"]), "players_data": [], "Opener": "", "Mastermind": "",
                         "Spell": "", "Worker": "", "Megamind": False, "MVP": False}
            for player in game["players_data"]:
                temp_dict["players_data"].append([player["player_name"], player["player_elo"], player["party_size"], player["player_id"]])
                if player["player_id"] == playerid:
                    if player["player_name"] != api_profile["playerName"]:
                        known_names.add(player["player_name"])
                    # Players
                    teammate = game["players_data"][player_map[player["player_slot"]][0]]
                    enemy1 = game["players_data"][player_map[player["player_slot"]][1]]
                    enemy2 = game["players_data"][player_map[player["player_slot"]][2]]
                    p: dict
                    for p in [[teammate, "Teammates"],[enemy1, "Enemies"],[enemy2, "Enemies"]]:
                        if p[0]["player_id"] in player_dict[p[1]]:
                            player_dict[p[1]][p[0]["player_id"]]["Count"] += 1
                            player_dict[p[1]][p[0]["player_id"]]["EloChange"] += player["elo_change"]
                        else:
                            player_dict[p[1]][p[0]["player_id"]] = {"Count": 1, "Wins": 0, "Playername": p[0]["player_name"], "Playerid": p[0]["player_id"], "EloChange": player["elo_change"]}
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
                    elochange["Overall"] += player["elo_change"]
                    elochange["SoloQ" if player["party_size"] == 1 else "DuoQ"] += player["elo_change"]
                    if (player["mvp_score"] > teammate["mvp_score"]) and game["ending_wave"] != 1:
                        temp_dict["MVP"] = True
                        mvp_count["Overall"] += 1
                        mvp_count["SoloQ" if player["party_size"] == 1 else "DuoQ"] += 1
                    if player["game_result"] == "won":
                        winlose["Overall"][0] += 1
                        winlose["SoloQ" if player["party_size"] == 1 else "DuoQ"][0] += 1
                    elif player["game_result"] == "lost":
                        winlose["Overall"][1] += 1
                        winlose["SoloQ" if player["party_size"] == 1 else "DuoQ"][1] += 1
                    temp_dict["Result_String"] = [player["game_result"], f"Wave {game["ending_wave"]}"]
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
        # Check if the profile owner has their flag hidden
        hide_flag_on_profile = False
        
        # Get the Discord ID of the profile owner
        conn = sqlite3.connect("site.db")
        cursor = conn.cursor()
        cursor.execute("SELECT discord_id, hide_country_flag FROM users WHERE player_id = ?", (playerid,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            profile_owner_discord_id, hide_flag = result
            hide_flag_on_profile = bool(hide_flag)
        
        # Get twitch and youtube usernames for this profile
        twitch_username = sitedb.get_twitch_username(playerid)
        youtube_username = sitedb.get_youtube_username(playerid)
        
        return render_template(
            "profile.html",
            api_profile=api_profile, api_stats=api_stats, get_rank_url=util.get_rank_url, winrate=util.custom_winrate,
            stats_list=stats_list, image_list=image_list, playername=playername, history=history_parsed, short_history = short_history,
            winlose=winlose, elochange=elochange, playerurl = f"/load/{playerid}", values=values,
            labels=labels, games=games, wave1 = wave1_percents, mms = mms, openers = openers, get_cdn = util.get_cdn_image, elo=elo,
            patch = patch, spells = spells, player_dict=player_dict, profile=True, plus_prefix=util.plus_prefix, patch_list = patches,
            player_rank=player_rank, refresh_in_progress=in_progress, cooldown_duration=cooldown_duration, playerid=playerid, mvp_count=mvp_count,
            known_names=known_names, hide_flag_on_profile=hide_flag_on_profile, is_own_profile=(user and user.get("player_id") == playerid),
            twitch_username=twitch_username, youtube_username=youtube_username
        )
    else:
        for szn in ["12", "11"]:
            if szn in patch.split(","):
                patch = szn
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
        get_db()
        drachbot_profile = drachbot_db.get_player_profile(playername)
        if drachbot_profile:
            playerid = drachbot_profile["playerid"]
            api_profile = drachbot_profile["api_profile"]
        else:
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
                    header_keys = ["Games", "Winrate", "Playrate", "Delta"]
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
                    header_keys = ["Games", "Winrate", "Playrate", "Delta"]
                    sub_headers = [["Champions", "Targets", "rollstats"], ["Openers", "Opener", "openstats"], ["Spells", "Spell", "spellstats"], ["Rolls", "Rolls", "rollstats"]]
                else:
                    header_keys = ["Games", "Winrate", "Playrate", "Delta"]
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
                    header_keys = ["Games", "Winrate", "Playrate", "Delta"]
                    sub_headers = [["Adds", "OpenWith", "unitstats"], ["MMs", "MMs", "mmstats"], ["Spells", "Spells", "spellstats"]]
                raw_data = drachbot.openstats.openstats(playerid, 0, elo, patch, data_only=True, history_raw=history_raw)
                games = raw_data[1]
                avg_elo = raw_data[2]
                raw_data = raw_data[0]
            case "matchupstats":
                title = f"{playername2}'s Match Up"
                title_image = "https://cdn.legiontd2.com/icons/ChallengerElite.png"
                header_title = "MM"
                header_cdn = "https://cdn.legiontd2.com/icons/Items/"
                if specific_key == "All":
                    header_keys = ["Games", "Winrate", "Pickrate", "Player Elo"]
                    sub_headers = [["Best With", "Teammates", "matchupstats"], ["Best Against", "Enemies", "matchupstats"]]
                else:
                    header_keys = ["Tier", "Games", "Winrate", "Delta"]
                    sub_headers = [["Teammate", "Teammates", "matchupstats"], ["Enemies", "Enemies", "matchupstats"],
                                   ["Sending To", "Enemies1", "matchupstats"], ["Receiving From", "Enemies2", "matchupstats"]]
                raw_data = drachbot.matchupstats.matchupstats(playerid, 0, patch, min_elo=elo, history_raw=history_raw)
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
                        header_keys = ["Games", "Winrate", "Playrate", "Delta"]
                        sub_headers = [["Targets", "Targets", "unitstats"], ["Openers", "Opener", "openstats"], ["MMs", "MMs", "mmstats"]]
                    else:
                        header_keys = ["Games", "Winrate", "Playrate", "Delta"]
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
                    header_keys = ["Games", "Winrate", "Playrate", "Delta"]
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
                    header_keys = ["Games", "Winrate", "Usage Rate", "Player Elo"]
                    sub_headers = [["Best Combo", "ComboUnit", "rollstats"], ["Best MMs", "MMs", "mmstats"], ["Best Spell", "Spells", "spellstats"]]
                else:
                    header_keys = ["Games", "Winrate", "Playrate", "Delta"]
                    sub_headers = [["Combos", "ComboUnit", "rollstats"], ["MMs", "MMs", "mmstats"], ["Spells", "Spells", "spellstats"]]
                raw_data = drachbot.unitstats.unitstats(playerid, 0, elo, patch, unit=specific_key.lower(), data_only=True, rollstats=True, history_raw=history_raw)
                games = raw_data[1]
                avg_elo = raw_data[2]
                raw_data = raw_data[0]
            case "sendstats":
                title = f"{playername2}'s Send"
                title_image = "https://cdn.legiontd2.com/icons/Brute.png"
                header_title = "Send"
                header_cdn = "https://cdn.legiontd2.com/icons/"
                if specific_key == "All":
                    header_keys = ["Sends", "Winrate", "Sendrate*"]
                    sub_headers = [["Best Wave", "Waves", "wavestats"], ["Best Into", "Units", "unitstats"], ["Best With*", "MercsCombo", "sendstats"]]
                else:
                    header_keys = ["Sends", "Winrate"]
                    sub_headers = [["Waves", "Waves", "wavestats"], ["Units", "Units", "unitstats"], ["Combo", "MercsCombo", "sendstats"]]
                raw_data = drachbot.sendstats.sendstats(playerid, history_raw=history_raw)
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
            if stats == "mmstats" or stats == "megamindstats":
                new_dict = {}
                for key in raw_data:
                    if raw_data[key]["Count"] == 0 and (key == "DoubleLockIn" or key == "Scrapper"):
                        continue
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
                                   get_rank_url=util.get_rank_url, get_avg_end_wave=util.get_avg_end_wave,playerurl=f"/profile/{playername}", playername2=playername2, patch_selector=True,
                                   title=title, title_image=title_image, header_title=header_title, player_avatar_url = api_profile["avatarUrl"], plus_prefix=util.plus_prefix)
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
                               playerurl = f"/profile/{playername}", playername2=f"{playername2} ", patch_selector=True, playerprofile = True, player_avatar_url = api_profile["avatarUrl"],
                               plus_prefix=util.plus_prefix)

@app.route('/<stats>/', defaults={"elo": defaults[1], "patch": defaults[0], "specific_key": "All"})
@app.route('/<stats>/<patch>/<elo>/', defaults={"specific_key": "All"})
@app.route('/<stats>/<patch>/<elo>/<specific_key>')
@cache.cached(timeout=timeout)
def stats(stats, elo, patch, specific_key):
    elo = str(elo)
    games = 0
    avg_elo = elo
    elo1 = elo
    elo2 = None
    if "-" in elo:
        elo1 = elo.split("-")[0]
        elo2 = elo.split("-")[1]
    playername2=""
    if stats not in website_stats:
        return render_template("no_data.html", text="Page not found.")
    raw_data = {}
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
                header_keys = ["Tier", "Games", "Winrate", "Playrate", "Delta"]
                sub_headers = [["Champions", "Targets", "unitstats"],["Openers", "Opener", "openstats"], ["Spells", "Spell", "spellstats"], ["Rolls", "Rolls", "rollstats"]]
            else:
                header_keys = ["Tier", "Games", "Winrate", "Playrate", "Delta"]
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
                header_keys = ["Tier", "Games", "Winrate", "Playrate", "Delta"]
                sub_headers = [["Champions", "Targets", "rollstats"],["Openers", "Opener", "openstats"], ["Spells", "Spell", "spellstats"], ["Rolls", "Rolls", "rollstats"]]
            else:
                header_keys = ["Tier", "Games", "Winrate", "Playrate", "Delta"]
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
                header_keys = ["Tier", "Games", "Winrate", "Playrate", "Delta"]
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
                    header_keys = ["Tier", "Games", "Winrate", "Playrate", "Delta"]
                    sub_headers = [["Targets", "Targets", "unitstats"], ["Openers", "Opener", "openstats"], ["MMs", "MMs", "mmstats"]]
                else:
                    header_keys = ["Tier", "Games", "Winrate", "Playrate", "Delta"]
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
                header_keys = ["Tier", "Games", "Winrate", "Playrate", "Delta"]
                sub_headers = [["Combos", "ComboUnit", "unitstats"], ["MMs", "MMs", "mmstats"], ["Spells", "Spells", "spellstats"]]
            folder = "unitstats"
        case "rollstats":
            title = "Roll"
            title_image = "https://cdn.legiontd2.com/icons/Reroll.png"
            header_title = "Roll"
            header_cdn = "https://cdn.legiontd2.com/icons/"
            if specific_key == "All":
                header_keys = ["Tier", "Games", "Winrate", "Usage Rate", "Player Elo"]
                sub_headers = [["Best Combo", "ComboUnit", "rollstats"], ["Best MMs", "MMs", "mmstats"], ["Best Spell", "Spells", "spellstats"]]
            else:
                header_keys = ["Tier", "Games", "Winrate", "Playrate", "Delta"]
                sub_headers = [["Combos", "ComboUnit", "rollstats"], ["MMs", "MMs", "mmstats"], ["Spells", "Spells", "spellstats"]]
            folder = "rollstats"
        case "wavestats":
            title = "Wave"
            title_image = "https://cdn.legiontd2.com/icons/LegionKing.png"
            header_title = "Wave"
            header_cdn = "https://cdn.legiontd2.com/icons/"
            if specific_key == "All":
                header_keys = ["Endrate", "Sendrate", "Avg Leak"]
                sub_headers = [["Best Send", "Mercs", "sendstats"], ["Best Unit", "Units", "unitstats"]]
            else:
                header_keys = ["Games", "Winrate", "Playrate"]
                sub_headers = [["Sends", "Mercs", "sendstats"], ["Units", "Units", "unitstats"]]
            folder = "wavestats"
        case "matchupstats":
            title = "Match Up"
            title_image = "https://cdn.legiontd2.com/icons/ChallengerElite.png"
            header_title = "MM"
            header_cdn = "https://cdn.legiontd2.com/icons/Items/"
            if specific_key == "All":
                header_keys = ["Games", "Winrate", "Pickrate", "Player Elo"]
                sub_headers = [["Best With", "Teammates", "matchupstats"], ["Best Against", "Enemies", "matchupstats"]]
            else:
                header_keys = ["Tier", "Games", "Winrate", "Synergy", "Delta"]
                sub_headers = [["Teammate", "Teammates", "matchupstats"], ["Enemies", "Enemies", "matchupstats"],
                               ["Sending To", "Enemies1", "matchupstats"], ["Receiving From", "Enemies2", "matchupstats"]]
            folder = "matchupstats"
        case "gamestats":
            title = "Game"
            title_image = "https://cdn.legiontd2.com/icons/DefaultAvatar.png"
            header_title = "Game"
            folder = "gamestats"
        case "sendstats":
            title = "Send"
            title_image = "https://cdn.legiontd2.com/icons/Brute.png"
            header_title = "Send"
            header_cdn = "https://cdn.legiontd2.com/icons/"
            if specific_key == "All":
                header_keys = ["Sends", "Winrate", "Sendrate*"]
                sub_headers = [["Best Wave", "Waves", "wavestats"], ["Best Into", "Units", "unitstats"], ["Best With*", "MercsCombo", "sendstats"]]
            else:
                header_keys = ["Sends", "Winrate"]
                sub_headers = [["Waves", "Waves", "wavestats"], ["Units", "Units", "unitstats"], ["Combo", "MercsCombo", "sendstats"]]
            folder = "sendstats"
    mod_date = None
    # ALLOWING CUSTOM PATCH
    if patch.startswith("v"):
        if not validate_custom_patch(patch):
            return render_template("no_data.html", text=f"Unsupported query")
        path = f"Files/player_cache/All_{patch}_{elo}.msgpack"
        history_raw = None
        if os.path.isfile(path):
            mod_date2 = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)
            date_diff = datetime.now(tz=timezone.utc) - mod_date2
            minutes_diff = date_diff.total_seconds() / 60
            if minutes_diff > 120:
                os.remove(path)
            else:
                with open(path, "rb") as f:
                    history_raw = msgpack.unpackb(f.read(), raw=False)
        if not history_raw:
            get_db()
            req_columns = [[GameData.game_id, GameData.queue, GameData.date, GameData.version, GameData.ending_wave, GameData.game_elo, GameData.player_ids, GameData.spell_choices, GameData.game_length,
                            PlayerData.player_id, PlayerData.player_slot, PlayerData.game_result, PlayerData.player_elo, PlayerData.legion, PlayerData.opener, PlayerData.spell,
                            PlayerData.workers_per_wave, PlayerData.megamind, PlayerData.build_per_wave, PlayerData.champ_location, PlayerData.spell_location, PlayerData.fighters,
                            PlayerData.mercs_sent_per_wave, PlayerData.leaks_per_wave, PlayerData.kingups_sent_per_wave, PlayerData.fighter_value_per_wave, PlayerData.income_per_wave],
                           ["game_id", "queue", "date", "version", "ending_wave", "game_elo", "spell_choices", "game_length"],
                           ["player_id", "player_slot", "game_result", "player_elo", "legion", "opener", "spell", "workers_per_wave", "megamind", "build_per_wave",
                            "champ_location", "spell_location", "fighters", "mercs_sent_per_wave", "leaks_per_wave", "kingups_sent_per_wave", "fighter_value_per_wave",
                            "income_per_wave"]]
            history_raw = drachbot_db.get_matchistory("all", 0, int(elo1), patch[1:], earlier_than_wave10=True, req_columns=req_columns)
            if len(history_raw) == 0:
                return render_template("no_data.html", text=f"No Data for {patch}")
            with open(path, "wb") as f:
                f.write(msgpack.packb(history_raw, default=str))
        if stats != "gamestats":
            match stats:
                case "megamindstats":
                    raw_data = drachbot.mmstats.mmstats("all",0, int(elo1), patch[1:],"Megamind", data_only=True, history_raw=history_raw)
                case "mmstats":
                    raw_data = drachbot.mmstats.mmstats("all", 0, int(elo1), patch[1:], data_only=True, history_raw=history_raw)
                case "openstats":
                    raw_data = drachbot.openstats.openstats("all", 0, int(elo1), patch[1:], data_only=True, history_raw=history_raw)
                case "spellstats":
                    raw_data = drachbot.spellstats.spellstats("all", 0, int(elo1), patch[1:], data_only=True, history_raw=history_raw)
                case "unitstats":
                    raw_data = drachbot.unitstats.unitstats("all", 0, int(elo1), patch[1:], data_only=True, history_raw=history_raw)
                case "rollstats":
                    raw_data = drachbot.unitstats.unitstats("all", 0, int(elo1), patch[1:], data_only=True, rollstats=True, history_raw=history_raw)
                case "matchupstats":
                    raw_data = drachbot.matchupstats.matchupstats("all", 0, patch[1:], min_elo=int(elo1), history_raw=history_raw)
                case "wavestats":
                    raw_data = drachbot.wavestats.wavestats("all", 0, int(elo1), patch[1:], history_raw=history_raw)
                case "sendstats":
                    raw_data = drachbot.sendstats.sendstats("all", history_raw=history_raw)
            games = raw_data[1]
            avg_elo = raw_data[2]
            raw_data = raw_data[0]
        else:
            raw_data = drachbot.gamestats.gamestats("all", history_raw)
            games = raw_data[3]
            avg_elo = raw_data[4]
            raw_data = {"Wave1Stats": raw_data[1], "GameLength": raw_data[2], "WaveDict": raw_data[0]}
        if type(raw_data) == str:
            return render_template("no_data.html", text=f"No Data for {patch}")
    else:
        if elo1 and elo2:
            for file in os.listdir(shared_folder + f"data/{folder}/"):
                if file.startswith(f"{patch}_{elo1}"):
                    games = file.split("_")[2]
                    try:
                        games = int(games)
                    except Exception:
                        return render_template("no_data.html", text="No Data")
                    avg_elo = file.split("_")[3].replace(".msgpack", "")
                    with open(shared_folder + f"data/{folder}/" + file, "rb") as f:
                        mod_date = util.time_ago(datetime.fromtimestamp(os.path.getmtime(shared_folder + f"data/{folder}/" + file)).timestamp())
                        raw_data = msgpack.unpackb(f.read(), raw=False)
        else:
            for file in os.listdir(shared_folder + f"data/{folder}/"):
                file_name_split = file.split("_")
                file_patch = file_name_split[0]
                try:
                    file_elo = int(file_name_split[1])
                    file_games = int(file_name_split[2])
                except ValueError:
                    continue

                file_avg_elo = file_name_split[3].replace(".msgpack", "")

                if file_patch == patch and file_elo >= int(elo):
                    games += file_games
                    with open(shared_folder + f"data/{folder}/" + file, "rb") as f:
                        mod_date = util.time_ago(datetime.fromtimestamp(os.path.getmtime(shared_folder + f"data/{folder}/" + file)).timestamp())
                        temp_data = msgpack.unpackb(f.read(), raw=False)
                        raw_data = util.merge_dicts(raw_data, temp_data)
            avg_elo = f"{elo}+"
            if stats != "gamestats":
                sort_key = "Count" if stats != "wavestats" else "EndCount"
                new_index = sorted(raw_data, key=lambda x: raw_data[x][sort_key], reverse=True)
                raw_data = {k: raw_data[k] for k in new_index}
    if raw_data:
        if stats != "mmstats" and stats != "gamestats":
            new_dict = {}
            for key in raw_data:
                if raw_data[key]["Count"] != 0:
                    new_dict[key] = raw_data[key]
            raw_data = new_dict
        if stats == "mmstats" or stats == "megamindstats":
            new_dict = {}
            for key in raw_data:
                if raw_data[key]["Count"] == 0 and (key == "DoubleLockIn" or key == "Scrapper"):
                    continue
                new_dict[key] = raw_data[key]
            raw_data = new_dict
    if not raw_data or ((stats != "mmstats" and stats != "megamindstats") and specific_key != "All" and specific_key not in raw_data):
        return render_template("no_data.html", text="No Data")
    if stats == "megamindstats" and (specific_key != "All" and specific_key != "Megamind") and specific_key not in raw_data:
        return render_template("no_data.html", text="No Data")
    if stats == "mmstats" and specific_key != "Megamind":
        try:
            if specific_key != "All" and raw_data[specific_key]["Count"] == 0:
                return render_template("no_data.html", text="No Data")
        except KeyError:
            return render_template("no_data.html", text=f"{specific_key} not found")
    if stats == "gamestats":
        return render_template("gamestats.html", data=raw_data, elo_brackets=elos2, custom_winrate=util.custom_winrate,
                               games=games, avg_elo=avg_elo, patch=patch, patch_list=patches, elo=elo, custom_divide=util.custom_divide,
                               human_format=util.human_format, get_perf_list=util.get_perf_list, get_dict_value=util.get_dict_value,
                               specific_key=specific_key, get_unit_name=util.get_unit_name, sort_dict=util.sort_dict, get_gamestats_values =util.get_gamestats_values,
                               stats=stats, get_key_value=util.get_key_value, get_cdn_image=util.get_cdn_image, mm_list=mm_list,
                               mod_date=mod_date, get_tooltip=util.get_tooltip, get_rank_url=util.get_rank_url, get_avg_end_wave=util.get_avg_end_wave,
                               playerurl="", playername2=playername2, patch_selector=False, title=title, title_image=title_image, header_title=header_title, plus_prefix=util.plus_prefix)
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
    return render_template(html_file, data=raw_data, elo_brackets=elos2, custom_winrate=util.custom_winrate,
                           games=games, avg_elo = avg_elo, patch = patch, patch_list=patches, elo = elo, custom_divide = util.custom_divide,
                           human_format= util.human_format, get_perf_list=util.get_perf_list, get_dict_value=util.get_dict_value,
                           specific_key=specific_key, get_unit_name=util.get_unit_name, sort_dict=util.sort_dict, title=title, title_image=title_image,
                           stats=stats, header_cdn=header_cdn, header_title=header_title, header_keys=header_keys, get_key_value=util.get_key_value,
                           sub_headers=sub_headers, get_cdn_image=util.get_cdn_image, mm_list=mm_list, mod_date=mod_date, get_tooltip=util.get_tooltip,
                           data_keys = raw_data.keys(), get_rank_url=util.get_rank_url, get_avg_end_wave=util.get_avg_end_wave, specific_tier=specific_tier,
                           playerurl = "", playername2=playername2, patch_selector = False, plus_prefix=util.plus_prefix)


if __name__ == "__main__":
    if platform.system() == "Windows":
        #run_leaderboard_task_in_thread()
        for file in os.listdir("Files/player_cache"):
            os.remove(f"Files/player_cache/{file}")
        app.run(host="0.0.0.0", debug=True)
    else:
        from waitress import serve
        scheduler.add_job(id = 'Scheduled Task', func=run_leaderboard_task_in_thread, trigger="interval", seconds=180)
        scheduler.start()
        for file in os.listdir("Files/player_cache"):
            os.remove(f"Files/player_cache/{file}")
        serve(app, host="0.0.0.0", port=54937, threads=50)