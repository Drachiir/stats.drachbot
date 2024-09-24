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
from drachbot.peewee_pg import PlayerProfile, GameData, PlayerData
import requests

with open('Files/json/Secrets.json', 'r') as f:
    secret_file = json.load(f)
    f.close()

header = {'x-api-key': secret_file.get('apikey')}

def api_call_logger(request_type):
    try:
        with open("Files/json/api_calls.json", "r") as file:
            api_call_dict = json.load(file)
        date = datetime.now()
        if "next_reset" not in api_call_dict:
            api_call_dict["next_reset"] = (date + timedelta(days=1)).strftime("%m/%d/%Y")
        elif datetime.strptime(api_call_dict["next_reset"], "%m/%d/%Y") < datetime.now():
            api_call_dict = {"next_reset": (date + timedelta(days=1)).strftime("%m/%d/%Y")}
        if request_type not in api_call_dict:
            api_call_dict[request_type] = 1
        else:
            api_call_dict[request_type] += 1
        with open("Files/json/api_calls.json", "w") as file:
            json.dump(api_call_dict, file)
    except Exception:
        traceback.print_exc()

def get_leaderboard(num):
    url = f'https://apiv2.legiontd2.com/players/stats?limit={num}&sortBy=overallElo&sortDirection=-1'
    api_response = requests.get(url, headers=header)
    return json.loads(api_response.text)

def getprofile(playername):
    request_type = 'players/byName/'
    url = 'https://apiv2.legiontd2.com/' + request_type + playername
    try:
        api_response = requests.get(url, headers=header)
        if 'Limit Exceeded' in api_response.text:
            return 1
        api_response.raise_for_status()
    except requests.exceptions.HTTPError:
        return 0
    else:
        api_call_logger(request_type)
        profile = json.loads(api_response.text)
        return profile

def getstats(playerid):
    request_type = 'players/stats/'
    url = 'https://apiv2.legiontd2.com/' + request_type + playerid
    api_response = requests.get(url, headers=header)
    stats = json.loads(api_response.text)
    api_call_logger(request_type)
    return stats

def pullgamedata(playerid, offset, expected):
    ranked_count = 0
    games_count = 0
    url = 'https://apiv2.legiontd2.com/players/matchHistory/' + str(playerid) + '?limit=' + str(50) + '&offset=' + str(offset) + '&countResults=false'
    print('Pulling ' + str(50) + ' games from API...')
    api_response = requests.get(url, headers=header)
    api_call_logger("players/matchHistory/")
    raw_data = json.loads(api_response.text)
    print('Saving ranked games.')
    for x in raw_data:
        if ranked_count == expected:
            break
        if (raw_data == {'message': 'Internal server error'}) or (raw_data == {'err': 'Entry not found.'}):
            break
        if (x['queueType'] == 'Normal'):
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