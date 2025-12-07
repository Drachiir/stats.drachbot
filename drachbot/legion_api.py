import datetime
import json
import pathlib
import random
import time
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
import drachbot.peewee_pg as peewee_pg
import peewee
from drachbot.peewee_pg import PlayerProfile, GameData, PlayerData, db
import requests

with open('Files/json/Secrets.json', 'r') as f:
    secret_file = json.load(f)
    f.close()

header = {'x-api-key': secret_file.get('apikey')}

# API Call Tracking - Simple counter
API_CALLS_FILE = 'Files/json/api_calls.json'

def log_api_call(endpoint):
    """Log an API call to the tracking file."""
    try:
        # Load existing data
        try:
            with open(API_CALLS_FILE, 'r') as f:
                calls = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            calls = {}
        
        # Increment counter for this endpoint
        calls[endpoint] = calls.get(endpoint, 0) + 1
        
        # Save back to file
        with open(API_CALLS_FILE, 'w') as f:
            json.dump(calls, f, indent=2)
    except Exception as e:
        print(f"Error logging API call: {e}")

def get_leaderboard(num):
    url = f'https://apiv2.legiontd2.com/players/stats?limit={num}&sortBy=overallElo&sortDirection=-1'
    api_response = requests.get(url, headers=header)
    log_api_call("players/stats")
    return json.loads(api_response.text)

@db.atomic()
def getprofile(playername, by_id = False):
    if by_id:
        request_type = 'players/byId/'
        log_api_call("players/byId")
    else:
        request_type = 'players/byName/'
        log_api_call("players/byName")
    url = 'https://apiv2.legiontd2.com/' + request_type + playername
    try:
        api_response = requests.get(url, headers=header)
        if 'Limit Exceeded' in api_response.text:
            return 1
        api_response.raise_for_status()
    except requests.exceptions.HTTPError:
        return 0
    else:
        profile = json.loads(api_response.text)
        try:
            if PlayerProfile.get_or_none(PlayerProfile.player_id == profile["_id"]) is None:
                PlayerProfile(
                    player_id=profile["_id"],
                    player_name=profile["playerName"],
                    avatar_url=profile["avatarUrl"],
                    country=None,
                    guild_tag=None,
                    elo=None,
                    rank=None,
                    total_games_played=0,
                    ranked_wins_current_season=0,
                    ranked_losses_current_season=0,
                    ladder_points=0,
                    offset=0,
                    last_updated=datetime.now(tz=timezone.utc)
                ).save()
            else:
                PlayerProfile.update(
                    player_name=profile["playerName"],
                    avatar_url=profile["avatarUrl"],
                    last_updated=datetime.now()
                ).where(PlayerProfile.player_id == profile["_id"]).execute()
        except peewee.IntegrityError:
            pass
        return profile

def getstats(playerid):
    request_type = 'players/stats/'
    url = 'https://apiv2.legiontd2.com/' + request_type + playerid
    api_response = requests.get(url, headers=header)
    log_api_call("players/stats")
    stats = json.loads(api_response.text)
    return stats

def pullgamedata(playerid, offset, expected):
    ranked_count = 0
    games_count = 0
    url = 'https://apiv2.legiontd2.com/players/matchHistory/' + str(playerid) + '?limit=' + str(50) + '&offset=' + str(offset) + '&countResults=false'
    print('Pulling ' + str(50) + ' games from API...')
    api_response = requests.get(url, headers=header)
    log_api_call("players/matchHistory/")
    raw_data = json.loads(api_response.text)
    print('Saving ranked games.')
    for x in raw_data:
        if ranked_count == expected:
            break
        if (raw_data == {'message': 'Internal server error'}) or (raw_data == {'err': 'Entry not found.'}):
            break
        if x['queueType'] == 'Normal':
            if GameData.get_or_none(GameData.game_id == x["_id"]) is None:
                ranked_count += 1
                try:
                    peewee_pg.save_game(x)
                except peewee.IntegrityError as e:
                    print(e)
                    print(f"Peewee Integrity Error: {x["_id"]}")
                    break
        games_count += 1
    return [ranked_count, games_count]

def save_game_by_id(gameid):
    url = 'https://apiv2.legiontd2.com/games/byId/' + gameid + '?includeDetails=true'
    api_response = requests.get(url, headers=header)
    log_api_call("games/byId")
    x = json.loads(api_response.text)
    if (x == {'message': 'Internal server error'}) or (x == {'err': 'Entry not found.'}):
        return False
    try:
        peewee_pg.save_game(x)
        return True
    except peewee.IntegrityError as e:
        print(e)
        print(f"Peewee Integrity Error: {x["_id"]}")
        return False