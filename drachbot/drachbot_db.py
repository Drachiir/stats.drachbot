from pathlib import Path

import peewee
from peewee import fn
import drachbot.legion_api as legion_api
from drachbot.peewee_pg import PlayerProfile, GameData, PlayerData
from playhouse.postgres_ext import *
import datetime
from datetime import datetime, timezone
import requests

def get_playerid(playername):
    profile_data_query = (PlayerProfile
                          .select(PlayerProfile.player_name, PlayerProfile.player_id)
                          .where(fn.LOWER(PlayerProfile.player_name) == fn.LOWER(playername))
                          ).dicts()
    if profile_data_query.count() == 1:
        for row in profile_data_query:
            return row["player_id"]
    else:
        return None

def get_game_by_id(gameid):
    if GameData.get_or_none(GameData.game_id == gameid) is None:
        success = legion_api.save_game_by_id(gameid)
        if not success:
            return {"Error": "Game not found."}
    req_columns = [[GameData.game_id, GameData.queue, GameData.date, GameData.version, GameData.ending_wave, GameData.game_elo, GameData.player_ids,
                    GameData.spell_choices, GameData.left_king_hp, GameData.right_king_hp, GameData.player_count, GameData.game_length,
                    PlayerData.player_id, PlayerData.player_name, PlayerData.player_slot, PlayerData.game_result, PlayerData.player_elo, PlayerData.legion, PlayerData.opener, PlayerData.spell,
                    PlayerData.workers_per_wave, PlayerData.megamind, PlayerData.build_per_wave, PlayerData.champ_location, PlayerData.spell_location, PlayerData.fighters,
                    PlayerData.mercs_received_per_wave, PlayerData.leaks_per_wave, PlayerData.kingups_received_per_wave, PlayerData.fighter_value_per_wave, PlayerData.income_per_wave,
                    PlayerData.roll, PlayerData.net_worth_per_wave, PlayerData.elo_change, PlayerData.spell_location, PlayerData.champ_location],
                   ["game_id", "queue", "date", "version", "ending_wave", "game_elo", "spell_choices", "left_king_hp", "right_king_hp", "player_count", "game_length"],
                   ["player_id", "player_name", "player_slot", "game_result", "player_elo", "legion", "opener", "spell", "workers_per_wave", "megamind", "build_per_wave",
                    "champ_location", "spell_location", "fighters", "mercs_received_per_wave", "leaks_per_wave", "kingups_received_per_wave", "fighter_value_per_wave",
                    "income_per_wave", "roll", "net_worth_per_wave", "elo_change", "spell_location", "champ_location"]]
    game_data_query = (PlayerData
                       .select(*req_columns[0])
                       .join(GameData)
                       .where(GameData.game_id == gameid.casefold())).dicts()
    for i, row in enumerate(game_data_query.iterator()):
        p_data = {}
        for field in req_columns[2]:
            p_data[field] = row[field]
        if i % row["player_count"] == 0:
            temp_data = {}
            for field in req_columns[1]:
                temp_data[field] = row[field]
            temp_data["players_data"] = [p_data]
        else:
            try:
                temp_data["players_data"].append(p_data)
            except Exception:
                return {"Error": "Game not found."}
        if i % row["player_count"] == (row["player_count"]-1):
            try:
                if len(temp_data["players_data"]) == row["player_count"]:
                    temp_data["players_data"] = sorted(temp_data["players_data"], key=lambda x: x['player_slot'])
            except KeyError:
                return {"Error": "Game not found."}
    return temp_data
    
def get_games_loop(playerid, offset, expected, timeout_limit = 1):
    print("Starting get_games_loop, expecting " + str(expected) + " games.")
    data = legion_api.pullgamedata(playerid, offset, expected)
    count = data[0]
    games_count = data[1]
    timeout = 0
    while count < expected:
        if data[0] == 0:
            timeout += 1
        count += data[0]
        games_count += data[1]
        if timeout == timeout_limit:
            print('Timeout while pulling games.')
            break
        offset += 50
        data = legion_api.pullgamedata(playerid, offset, expected)
    else:
        print('All '+str(expected)+' required games pulled.')
    return games_count

def get_matchistory(playerid, games, min_elo=0, patch='0', update = 0, earlier_than_wave10 = False,
                    sort_by = "date", req_columns = [], profile = None, stats = None, pname = "",
                    skip_stats=False, get_new_games = False):
    patch_list = []
    if earlier_than_wave10:
        earliest_wave = 2
    else:
        earliest_wave = 11
    if sort_by == "date":
        sort_arg = GameData.date
    else:
        sort_arg = GameData.game_elo
    if patch != '0' and "-" not in patch and "+" not in patch:
        patch_list = patch.replace(" ", "").split(',')
    elif patch != "0" and "+" in patch and "-" not in patch:
        patch_new = patch.replace(" ", "").replace("+", "")
        if len(patch_new) == 5:
            patch_new = patch_new.split('.')
            for x in range(13 - int(patch_new[1])):
                if int(patch_new[1]) + x < 10:
                    prefix = "0"
                else:
                    prefix = ""
                patch_list.append(patch_new[0] + "." + prefix + str(int(patch_new[1]) + x))
        else:
            return []
    elif patch != "0" and "-" in patch:
        patch_new = patch.split("-")
        if len(patch_new) == 2:
            patch_new2 = patch_new[0].split('.')
            patch_new3 = patch_new[1].split('.')
            for x in range(int(patch_new3[1])-int(patch_new2[1])+1):
                if int(patch_new2[1]) + x < 10:
                    prefix = "0"
                else:
                    prefix = ""
                patch_list.append(patch_new2[0] + "." + prefix + str(int(patch_new2[1]) + x))
        else:
            return []
    games_count = 0
    if playerid != 'all':
        if not skip_stats:
            if PlayerProfile.get_or_none(PlayerProfile.player_id == playerid) is None:
                print(playerid + ' profile not found, creating new database entry...')
                new_profile = True
                if stats:
                    playerstats = stats
                else:
                    playerstats = legion_api.getstats(playerid)
                try:
                    wins = playerstats['rankedWinsThisSeason']
                except KeyError:
                    wins = 0
                try:
                    losses = playerstats['rankedLossesThisSeason']
                except KeyError:
                    losses = 0
                if profile:
                    playerprofile = profile
                else:
                    playerprofile = legion_api.getprofile(pname)
                offset = 0
                try:
                    ladder_points = playerstats["ladderPoints"]
                except KeyError:
                    ladder_points = 0
                try:
                    games_played = playerstats["gamesPlayed"]
                except KeyError:
                    games_played = 0
                try:
                    PlayerProfile(
                        player_id=playerid,
                        player_name=playerprofile["playerName"],
                        total_games_played=games_played,
                        ranked_wins_current_season=wins,
                        ranked_losses_current_season=losses,
                        ladder_points=ladder_points,
                        offset=offset,
                        last_updated=datetime.now(tz=timezone.utc)
                    ).save()
                except peewee.IntegrityError:
                    pass
                data = get_games_loop(playerid, 0, 100)
            else:
                new_profile = False
                if stats:
                    playerstats = stats
                else:
                    playerstats = legion_api.getstats(playerid)
                data = PlayerProfile.select().where(PlayerProfile.player_id == playerid).get()
                ranked_games_old = data.ranked_wins_current_season+data.ranked_losses_current_season
                try:
                    wins = playerstats['rankedWinsThisSeason']
                except KeyError:
                    wins = 0
                try:
                    losses = playerstats['rankedLossesThisSeason']
                except KeyError:
                    losses = 0
                try:
                    ladder_points = playerstats["ladderPoints"]
                except KeyError:
                    ladder_points = 0
                PlayerProfile.update(
                    ladder_points = ladder_points,
                    ranked_wins_current_season=wins,
                    ranked_losses_current_season=losses,
                    last_updated=datetime.now()
                ).where(PlayerProfile.player_id == playerid).execute()
                if profile:
                    PlayerProfile.update(
                        player_name=profile["playerName"]
                    ).where(PlayerProfile.player_id == playerid).execute()
                ranked_games = wins + losses
                games_diff = ranked_games - ranked_games_old
                if ranked_games_old < ranked_games:
                    games_count += get_games_loop(playerid, 0, games_diff)
                if games_count > 0:
                    PlayerProfile.update(offset=games_count+data.offset).where(PlayerProfile.player_id == playerid).execute()
        if update == 0:
            if get_new_games:
                get_games_loop(playerid, 0, 20)
            raw_data = []
            if patch == "11" or patch == "10":
                expr = GameData.version.startswith("v"+patch)
            elif patch != "0":
                expr = fn.Substr(GameData.version, 2, 5).in_(patch_list)
            else:
                expr = True
            game_data_query = (PlayerData
                         .select(*req_columns[0])
                         .join(GameData)
                         .where((GameData.queue == "Normal") & GameData.player_ids.contains(playerid) & (GameData.game_elo >= min_elo) & expr & (GameData.ending_wave >= earliest_wave))
                         .order_by(sort_arg.desc(), GameData.id.desc(), PlayerData.player_slot)).dicts()
            for i, row in enumerate(game_data_query.iterator()):
                p_data = {}
                for field in req_columns[2]:
                    p_data[field] = row[field]
                if i % 4 == 0:
                    temp_data = {}
                    for field in req_columns[1]:
                        temp_data[field] = row[field]
                    temp_data["players_data"] = [p_data]
                else:
                    try:
                        temp_data["players_data"].append(p_data)
                    except Exception:
                        pass
                if i % 4 == 3:
                    try:
                        if len(temp_data["players_data"]) == 4:
                            temp_data["players_data"] = sorted(temp_data["players_data"], key=lambda x: x['player_slot'])
                            raw_data.append(temp_data)
                            temp_data = {}
                    except KeyError:
                        temp_data = {}
    else:
        raw_data = []
        if patch == "11" or patch == "10":
            expr = GameData.version.startswith("v" + patch)
            if games == 0:
                games = GameData.select().where((GameData.queue == "Normal") & expr & (GameData.game_elo >= min_elo) & (GameData.ending_wave >= earliest_wave)).count()
        elif patch != "0":
            if len(patch_list) == 1:
                expr = fn.Substr(GameData.version, 2, len(patch_list[0])).in_(patch_list)
            else:
                expr = fn.Substr(GameData.version, 2, 5).in_(patch_list)
            if games == 0:
                games = GameData.select().where((GameData.queue == "Normal") & expr & (GameData.game_elo >= min_elo) & (GameData.ending_wave >= earliest_wave)).count()
        else:
            if games == 0:
                games = GameData.select().where((GameData.queue == "Normal") & (GameData.game_elo >= min_elo) & (GameData.ending_wave >= earliest_wave)).count()
            expr = True
        if games > 150000:
            games = 150000
        game_data_query = (PlayerData
                           .select(*req_columns[0])
                           .join(GameData)
                           .where((GameData.queue == "Normal") & expr & (GameData.game_elo >= min_elo) & (GameData.ending_wave >= earliest_wave))
                           .order_by(sort_arg.desc(), GameData.id.desc(), PlayerData.player_slot)
                           .limit(games * 4)).dicts()
        temp_data = {}
        for i, row in enumerate(game_data_query.iterator()):
            p_data = {}
            # if row["version"] == "v11.07":
            #     continue
            for field in req_columns[2]:
                p_data[field] = row[field]
            if i % 4 == 0:
                temp_data = {}
                for field in req_columns[1]:
                    temp_data[field] = row[field]
                temp_data["players_data"] = [p_data]
            else:
                try:
                    temp_data["players_data"].append(p_data)
                except Exception:
                    pass
            if i % 4 == 3:
                try:
                    if len(temp_data["players_data"]) == 4:
                        temp_data["players_data"] = sorted(temp_data["players_data"], key=lambda x: x['player_slot'])
                        raw_data.append(temp_data)
                        temp_data = {}
                except KeyError:
                    temp_data = {}
    if update == 0:
        return raw_data
    else:
        if new_profile:
            return data
        else:
            return games_diff
        