from pathlib import Path
import peewee
from peewee import fn
import drachbot.legion_api as legion_api
import util
from drachbot.peewee_pg import PlayerProfile, GameData, PlayerData, db
from playhouse.postgres_ext import *
import datetime
from datetime import datetime, timezone
import requests
from peewee import InterfaceError, OperationalError
from psycopg2 import OperationalError as Psycopg2OperationalError

@db.atomic()
def get_playerid(playername):
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

@db.atomic()
def get_player_profile(playername, by_id = False):
    try:
        if by_id:
            expr = fn.LOWER(PlayerProfile.player_id) == fn.LOWER(playername)
        else:
            expr = fn.LOWER(PlayerProfile.player_name) == fn.LOWER(playername)
        profile_data_query = (PlayerProfile
                              .select(PlayerProfile.player_id, PlayerProfile.player_name, PlayerProfile.country,
                                      PlayerProfile.guild_tag, PlayerProfile.avatar_url, PlayerProfile.rank, PlayerProfile.elo, PlayerProfile.city)
                              .where(expr)
                              .dicts())
        rows = list(profile_data_query)
        if len(rows) == 1:
            playerid = rows[0]["player_id"]
            api_profile = {"playerName": rows[0]["player_name"],
                           "avatarUrl": rows[0]["avatar_url"],
                           "guildTag": rows[0]["guild_tag"] if rows[0]["guild_tag"] else "",
                           "rank": rows[0]["rank"] if rows[0]["rank"] else 0,
                           "elo": rows[0]["elo"] if rows[0]["elo"] else 0}
            return {"playerid": playerid, "api_profile": api_profile, "country": rows[0]["country"], "city": rows[0]["city"]}
        else:
            return None
    except (InterfaceError, OperationalError, Psycopg2OperationalError) as e:
        print(f"Database error: {e}")
        return None

@db.atomic()
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
                    PlayerData.roll, PlayerData.net_worth_per_wave, PlayerData.elo_change, PlayerData.spell_location, PlayerData.champ_location, PlayerData.mvp_score, PlayerData.party_size,
                    PlayerData.double_down],
                   ["game_id", "queue", "date", "version", "ending_wave", "game_elo", "spell_choices", "left_king_hp", "right_king_hp", "player_count", "game_length"],
                   ["player_id", "player_name", "player_slot", "game_result", "player_elo", "legion", "opener", "spell", "workers_per_wave", "megamind", "build_per_wave",
                    "champ_location", "spell_location", "fighters", "mercs_received_per_wave", "leaks_per_wave", "kingups_received_per_wave", "fighter_value_per_wave",
                    "income_per_wave", "roll", "net_worth_per_wave", "elo_change", "spell_location", "champ_location", "mvp_score", "party_size", "double_down"]]
    game_data_query = (PlayerData
                       .select(*req_columns[0])
                       .join(GameData)
                       .where(GameData.game_id == gameid.casefold())).dicts()
    temp_data = {}
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

    if not temp_data:
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

@db.atomic()
def get_matchistory(playerid, games, min_elo=0, patch='0', update = 0, earlier_than_wave10 = False,
                    sort_by = "date", req_columns=None, playerprofile = None, playerstats = None, pname ="",
                    skip_stats=False, get_new_games = False, max_elo = 9001, skip_game_refresh = False, sort_players = True, include_wave_one_finishes = False):
    if req_columns is None:
        req_columns = []
    patch_list = parse_patch_string(patch)
    if earlier_than_wave10:
        earliest_wave = 1 if include_wave_one_finishes else 2
    else:
        earliest_wave = 11
    if sort_by == "date":
        sort_arg = GameData.date
    else:
        sort_arg = GameData.game_elo

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
                        city=playerstats["city"],
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
                    city=playerstats["city"] if playerstats["city"] else data.city,
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
                timeout_limit = 1
                if games_diff > 200:
                    games_diff = 200
                if util.is_special_player(playerid) and games_diff > 10:
                    timeout_limit = 0
                    games_diff = 10
                if not skip_game_refresh:
                    if ranked_games_old < ranked_games:
                        games_count += get_games_loop(playerid, 0, games_diff, timeout_limit=timeout_limit)
                    if games_count > 0:
                        PlayerProfile.update(offset=min(500, games_count+data.offset)).where(PlayerProfile.player_id == playerid).execute()
        if update == 0:
            if get_new_games:
                get_games_loop(playerid, 0, 20)
            raw_data = []
            if patch in ["12", "11", "10", "26", "27"]:
                expr = GameData.version.startswith("v"+patch)
            elif patch != "0":
                if len(patch_list) == 1:
                    expr = fn.Substr(GameData.version, 2, len(patch_list[0])).in_(patch_list)
                else:
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
        if patch in ["12", "11", "10", "26", "27"]:
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
        if games > 200000:
            games = 200000
        game_data_query = (PlayerData
                           .select(*req_columns[0])
                           .join(GameData)
                           .where((GameData.queue == "Normal") & expr & ((GameData.game_elo >= min_elo) & (GameData.game_elo <= max_elo)) & (GameData.ending_wave >= earliest_wave))
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

@db.atomic()
def get_search_results(search_term):
    query = (PlayerProfile
             .select(PlayerProfile.player_name, PlayerProfile.avatar_url, PlayerProfile.player_id)
             .where(fn.LOWER(PlayerProfile.player_name).contains(search_term.lower()))
             .limit(5))

    players = [{'player_name': player.player_name,
                'avatar_url': player.avatar_url,
                "player_id": player.player_id}
               for player in query]
    return players


def _parse_patch(patch_str):
    """Parse patch string into (major, minor) tuple."""
    parts = patch_str.strip().split('.')
    if len(parts) == 2:
        return int(parts[0]), int(parts[1])
    raise ValueError(f"Invalid patch format: {patch_str}")


def _format_patch(major, minor, use_old_format=False):
    """
    Format patch version.
    Old format (use_old_format=True): always two digits (X.00, X.01, ..., X.11) - range 0-11
    New format (use_old_format=False): single digit for 1-9, two digits for 10-12 (X.1, X.2, ..., X.9, X.10, X.11, X.12) - range 1-12
    """
    if use_old_format:
        return f"{major}.{minor:02d}"
    else:
        # New format: single digit for 1-9, two digits for 10-12
        if minor < 10:
            return f"{major}.{minor}"
        else:
            return f"{major}.{minor:02d}"


def _detect_format(patch_str):
    """Detect if patch uses old format (X.00) or new format (X.1)."""
    parts = patch_str.strip().split('.')
    if len(parts) == 2:
        minor_str = parts[1]
        # Old format: minor version has leading zero (e.g., "00", "01", "05")
        # New format: minor version is single digit 1-9 or starts with 1 (e.g., "1", "2", "10")
        return len(minor_str) == 2 and minor_str[0] == '0'
    return False


def parse_patch_string(patch):
    """
    Parse patch string into a list of patch versions.
    Supports comma-separated lists, plus notation (X.1+), and range notation (X.1-Y.5).
    Handles both old format (X.00-X.11) and new format (X.1-X.12).
    Returns empty list if patch is '0' or invalid.
    """
    if patch == '0':
        return []

    patch_list = []

    if "-" not in patch and "+" not in patch:
        # If no comma, just pass the patch string directly without parsing
        if ',' not in patch:
            patch_list.append(patch)
        else:
            # Comma-separated list: handle both X.00 and X.1 formats
            # Normalize all to two-digit format for consistency in database queries
            for p in patch.replace(" ", "").split(','):
                try:
                    major, minor = _parse_patch(p)
                    # Skip major versions 13-25 (season 12 ends at 12, season 26 starts at 26)
                    if 13 <= major <= 25:
                        continue
                    # Normalize to two-digit format for database matching
                    patch_list.append(f"{major}.{minor:02d}")
                except ValueError:
                    continue
    elif "+" in patch and "-" not in patch:
        # Plus notation: e.g., "25.1+" or "25.00+" generates patches up to end of range
        # Old format: .00 to .11 (0-11), New format: .1 to .12 (1-12)
        patch_new = patch.replace(" ", "").replace("+", "")
        print(patch_new)
        try:
            major, minor = _parse_patch(patch_new)
            # Skip major versions 13-25 (season 12 ends at 12, season 26 starts at 26)
            if 13 <= major <= 25:
                return []

            use_old_format = _detect_format(patch_new)

            # Old format: 0-11 (12 patches), New format: 1-12 (12 patches)
            max_minor = 11 if use_old_format else 12
            min_minor = 0 if use_old_format else 1

            for current_minor in range(minor, max_minor + 1):
                patch_list.append(_format_patch(major, current_minor, use_old_format=use_old_format))
        except (ValueError, IndexError):
            return []
    elif "-" in patch:
        # Range notation: e.g., "25.1-26.5" or "25.00-26.05"
        # Old format: .00 to .11 (0-11), New format: .1 to .12 (1-12)
        patch_new = patch.split("-")
        if len(patch_new) == 2:
            try:
                start_major, start_minor = _parse_patch(patch_new[0].strip())
                end_major, end_minor = _parse_patch(patch_new[1].strip())

                # Detect format from start patch
                use_old_format = _detect_format(patch_new[0].strip())

                # Define range limits based on format
                max_minor = 11 if use_old_format else 12
                min_minor = 0 if use_old_format else 1

                for major in range(start_major, end_major + 1):
                    # Skip major versions 13-25 (season 12 ends at 12, season 26 starts at 26)
                    if 13 <= major <= 25:
                        continue

                    if major == start_major:
                        # First major version: from start_minor to max_minor (inclusive)
                        for minor in range(start_minor, max_minor + 1):
                            patch_list.append(_format_patch(major, minor, use_old_format=use_old_format))
                    elif major == end_major:
                        # Last major version: from min_minor to end_minor (inclusive)
                        for minor in range(min_minor, end_minor + 1):
                            patch_list.append(_format_patch(major, minor, use_old_format=use_old_format))
                    else:
                        # Middle major versions: all patches from min_minor to max_minor (inclusive)
                        for minor in range(min_minor, max_minor + 1):
                            patch_list.append(_format_patch(major, minor, use_old_format=use_old_format))
            except (ValueError, IndexError):
                return []
        else:
            return []

    return patch_list