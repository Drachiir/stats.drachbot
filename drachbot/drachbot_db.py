from pathlib import Path
import peewee
from peewee import fn
import drachbot.legion_api as legion_api
from drachbot.peewee_pg import PlayerProfile, GameData, PlayerData, db
from playhouse.postgres_ext import *
import datetime
from datetime import datetime, timezone
import requests
from peewee import InterfaceError, OperationalError
from psycopg2 import OperationalError as Psycopg2OperationalError

def get_playerid(playername):
    with db.atomic():
        try:
            profile_data_query = (PlayerProfile
                                  .select(PlayerProfile.player_id)
                                  .where(fn.LOWER(PlayerProfile.player_name) == fn.LOWER(playername))
                                  .dicts())
            rows = list(profile_data_query)
            if len(rows) == 1:
                return rows[0]["player_id"]
            else:
                return None
        except (InterfaceError, OperationalError, Psycopg2OperationalError) as e:
            print(f"Database error: {e}")
            return None

def get_player_profile(playername):
    with db.atomic():
        try:
            profile_data_query = (PlayerProfile
                                  .select(PlayerProfile.player_id, PlayerProfile.player_name, PlayerProfile.country,
                                          PlayerProfile.guild_tag, PlayerProfile.avatar_url, PlayerProfile.rank, PlayerProfile.elo)
                                  .where(fn.LOWER(PlayerProfile.player_name) == fn.LOWER(playername))
                                  .dicts())
            rows = list(profile_data_query)
            if len(rows) == 1:
                playerid = rows[0]["player_id"]
                api_profile = {"playerName": rows[0]["player_name"],
                               "avatarUrl": rows[0]["avatar_url"],
                               "guildTag": rows[0]["guild_tag"] if rows[0]["guild_tag"] else "",
                               "rank": rows[0]["rank"] if rows[0]["rank"] else 0,
                               "elo": rows[0]["elo"] if rows[0]["elo"] else 0}
                return {"playerid": playerid, "api_profile": api_profile, "country": rows[0]["country"]}
            else:
                return None
        except (InterfaceError, OperationalError, Psycopg2OperationalError) as e:
            print(f"Database error: {e}")
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
                    PlayerData.roll, PlayerData.net_worth_per_wave, PlayerData.elo_change, PlayerData.spell_location, PlayerData.champ_location, PlayerData.mvp_score, PlayerData.party_size],
                   ["game_id", "queue", "date", "version", "ending_wave", "game_elo", "spell_choices", "left_king_hp", "right_king_hp", "player_count", "game_length"],
                   ["player_id", "player_name", "player_slot", "game_result", "player_elo", "legion", "opener", "spell", "workers_per_wave", "megamind", "build_per_wave",
                    "champ_location", "spell_location", "fighters", "mercs_received_per_wave", "leaks_per_wave", "kingups_received_per_wave", "fighter_value_per_wave",
                    "income_per_wave", "roll", "net_worth_per_wave", "elo_change", "spell_location", "champ_location", "mvp_score", "party_size"]]
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
                    sort_by = "date", req_columns=None, playerprofile = None, playerstats = None, pname ="",
                    skip_stats=False, get_new_games = False, max_elo = 9001, skip_game_refresh = False, sort_players = True):
    if req_columns is None:
        req_columns = []
    patch_list = []
    if earlier_than_wave10:
        earliest_wave = 2
    else:
        earliest_wave = 11
    if sort_by == "date":
        sort_arg = GameData.date
    else:
        sort_arg = GameData.game_elo
    if patch != "0":
        if "-" not in patch and "+" not in patch:
            patch_list = patch.replace(" ", "").split(',')
        elif "+" in patch and "-" not in patch:
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
        elif "-" in patch:
            patch_new = patch.split("-")
            if len(patch_new) == 2:
                start_major, start_minor = map(int, patch_new[0].split('.'))
                end_major, end_minor = map(int, patch_new[1].split('.'))

                for major in range(start_major, end_major + 1):
                    if major == start_major:
                        for minor in range(start_minor, 12):
                            prefix = "0" if minor < 10 else ""
                            patch_list.append(f"{major}.{prefix}{minor}")
                    elif major == end_major:
                        for minor in range(0, end_minor + 1):
                            prefix = "0" if minor < 10 else ""
                            patch_list.append(f"{major}.{prefix}{minor}")
                    else:
                        for minor in range(0, 12):
                            prefix = "0" if minor < 10 else ""
                            patch_list.append(f"{major}.{prefix}{minor}")
            else:
                return []
    games_count = 0
    if playerid != 'all':
        if not skip_stats:
            if PlayerProfile.get_or_none(PlayerProfile.player_id == playerid) is None:
                print(playerid + ' profile not found, creating new database entry...')
                new_profile = True
                try:
                    wins = playerstats['rankedWinsThisSeason']
                except KeyError:
                    wins = 0
                try:
                    losses = playerstats['rankedLossesThisSeason']
                except KeyError:
                    losses = 0
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
                        avatar_url=playerprofile["avatarUrl"],
                        country=playerstats["flag"],
                        guild_tag=playerprofile["guildTag"],
                        elo = playerstats["overallElo"],
                        rank = playerstats["playerRank"],
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
                    player_name=playerprofile["playerName"],
                    avatar_url=playerprofile["avatarUrl"],
                    country=playerstats["flag"] if playerstats["flag"] else data.country,
                    guild_tag=playerprofile["guildTag"] if playerprofile["guildTag"] else data.guild_tag,
                    elo=playerstats["overallElo"],
                    rank=playerstats["playerRank"],
                    ladder_points = ladder_points,
                    ranked_wins_current_season=wins,
                    ranked_losses_current_season=losses,
                    last_updated=datetime.now()
                ).where(PlayerProfile.player_id == playerid).execute()
                ranked_games = wins + losses
                games_diff = ranked_games - ranked_games_old
                if not skip_game_refresh:
                    if ranked_games_old < ranked_games:
                        games_count += get_games_loop(playerid, 0, games_diff)
                    if games_count > 0:
                        PlayerProfile.update(offset=games_count+data.offset).where(PlayerProfile.player_id == playerid).execute()
        if update == 0:
            if get_new_games:
                get_games_loop(playerid, 0, 20)
            raw_data = []
            if patch in ["12", "11", "10"]:
                expr = GameData.version.startswith("v"+patch)
            elif patch != "0":
                expr = fn.Substr(GameData.version, 2, 5).in_(patch_list)
            else:
                expr = True
            game_data_query = (PlayerData
                         .select(*req_columns[0])
                         .join(GameData)
                         .where(GameData.player_ids.contains(playerid) & (GameData.queue == "Normal") & (GameData.game_elo >= min_elo) & expr & (GameData.ending_wave >= earliest_wave))
                         .order_by(sort_arg.desc())
                         ).dicts()

            if games != 0:
                game_data_query = game_data_query.limit(games*4)

            # def explain_query(query):
            #     sql, params = query.sql()
            #     explain_sql = "EXPLAIN ANALYZE " + sql
            #     with db.connection_context():
            #         result = db.execute_sql(explain_sql, params)
            #         return result.fetchall()
            #
            # explain_result = explain_query(game_data_query)
            #
            # for row in explain_result:
            #     print(row[0])

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
                            if sort_players:
                                temp_data["players_data"] = sorted(temp_data["players_data"], key=lambda x: x['player_slot'])
                            raw_data.append(temp_data)
                            temp_data = {}
                    except KeyError:
                        temp_data = {}
    else:
        raw_data = []
        if patch in ["12", "11", "10"]:
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
        game_data_query = (PlayerData
                           .select(*req_columns[0])
                           .join(GameData)
                           .where((GameData.queue == "Normal") & expr & (max_elo >= GameData.game_elo >= min_elo) & (GameData.ending_wave >= earliest_wave))
                           .order_by(sort_arg.desc(), GameData.id.desc(), PlayerData.player_slot)
                           .limit(games * 4)).dicts()
        temp_data = {}
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
    if update == 0:
        return raw_data
    else:
        if new_profile:
            return data
        else:
            return games_diff
        