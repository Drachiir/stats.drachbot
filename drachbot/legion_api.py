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

def get_leaderboard(num):
    url = f'https://apiv2.legiontd2.com/players/stats?limit={num}&sortBy=overallElo&sortDirection=-1'
    api_response = requests.get(url, headers=header)
    return json.loads(api_response.text)

@db.atomic()
def getprofile(playername, by_id = False):
    if by_id:
        request_type = 'players/byId/'
    else:
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
        profile = json.loads(api_response.text)
        PlayerProfile.update(
            player_name=profile["playerName"],
            avatar_url=profile["avatarUrl"],
            last_updated=datetime.now()
        ).where(PlayerProfile.player_id == profile["_id"]).execute()
        return profile

def getstats(playerid):
    request_type = 'players/stats/'
    url = 'https://apiv2.legiontd2.com/' + request_type + playerid
    api_response = requests.get(url, headers=header)
    stats = json.loads(api_response.text)
    return stats

def pullgamedata(playerid, offset, expected):
    ranked_count = 0
    games_count = 0
    url = 'https://apiv2.legiontd2.com/players/matchHistory/' + str(playerid) + '?limit=' + str(50) + '&offset=' + str(offset) + '&countResults=false'
    print('Pulling ' + str(50) + ' games from API...')
    api_response = requests.get(url, headers=header)
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