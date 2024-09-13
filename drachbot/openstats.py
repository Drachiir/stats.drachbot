import platform
import json
import difflib

import util
import drachbot.legion_api as legion_api

if platform.system() == "Linux":
    shared_folder = "/shared/Images/"
    shared2_folder = "/shared2/"
else:
    shared_folder = "shared/Images/"
    shared2_folder = "shared2/"

def openstats(playername, games, min_elo, patch, sort="date", unit = "all", data_only = False, transparent = False, history_raw = {}):
    unit_dict = {}
    unit = unit.lower()
    with open('Files/json/units.json', 'r') as f:
        units_json = json.load(f)
    for u_js in units_json:
        if u_js["totalValue"] != '':
            if u_js["unitId"] and 270 > int(u_js["totalValue"]) > 0:
                string = u_js["unitId"]
                string = string.replace('_', ' ')
                string = string.replace(' unit id', '')
                unit_dict[string] = {'Count': 0, 'Wins': 0, 'Worker': 0, 'Elo': 0, 'OpenWith': {}, 'MMs': {}, 'Spells': {}, "Cost": u_js["totalValue"]}
    unit_dict['pack rat nest'] = {'Count': 0, 'Wins': 0, 'Worker': 0, 'Elo': 0, 'OpenWith': {}, 'MMs': {}, 'Spells': {}, "Cost": 75}
    if unit != "all":
        if unit in util.slang:
            unit = util.slang.get(unit)
        if unit not in unit_dict:
            close_matches = difflib.get_close_matches(unit, list(unit_dict.keys()))
            if len(close_matches) > 0:
                unit = close_matches[0]
            else:
                return unit + " unit not found."
    novacup = False
    if playername == 'all':
        playerid = 'all'
    elif 'nova cup' in playername:
        novacup = True
        playerid = playername
    else:
        playerid = legion_api.getid(playername)
        if playerid == 0:
            return 'Player ' + playername + ' not found.'
        if playerid == 1:
            return 'API limit reached, you can still use "all" commands.'
    if type(history_raw) == str:
        return history_raw
    if len(history_raw) == 0:
        return 'No games found.'
    games = len(history_raw)
    if 'nova cup' in playerid:
        playerid = 'all'
    patches = set()
    gameelo_list = []
    for game in history_raw:
        if game["ending_wave"] < 4: continue
        patches.add(game["version"])
        gameelo_list.append(game["game_elo"])
        if playerid.lower() != 'all' and 'nova cup' not in playerid:
            for player in game["players_data"]:
                if player["player_id"] == playerid:
                    opener_ranked_raw = player["build_per_wave"][:4]
                    break
        else:
            opener_ranked_raw = []
            for i in range(4):
                opener_ranked_raw.extend(game["players_data"][i]["build_per_wave"][:4])
        opener_ranked = []
        for i, x in enumerate(opener_ranked_raw):
            opener_ranked.extend([[]])
            x = x.split("!")
            for y in x:
                string = y.split('_unit_id:')
                opener_ranked[i].append(string[0].replace('_', ' '))
        if playerid.lower() != 'all' and 'nova cup' not in playerid:
            for player in game["players_data"]:
                if player["player_id"] == playerid:
                    s = set()
                    try:
                        for x in range(4):
                            for y in opener_ranked[x]:
                                s.add(y)
                    except IndexError:
                        continue
                    for y in s:
                        try:
                            if y != opener_ranked[0][0]:
                                if y in unit_dict[opener_ranked[0][0]]['OpenWith']:
                                    unit_dict[opener_ranked[0][0]]['OpenWith'][y]['Count'] += 1
                                    if player["game_result"] == 'won':
                                        unit_dict[opener_ranked[0][0]]['OpenWith'][y]['Wins'] += 1
                                else:
                                    unit_dict[opener_ranked[0][0]]['OpenWith'][y] = {'Count': 1, 'Wins': 0}
                                    if player["game_result"] == 'won':
                                        unit_dict[opener_ranked[0][0]]['OpenWith'][y]['Wins'] += 1
                            else:
                                unit_dict[opener_ranked[0][0]]['Count'] += 1
                                if player["legion"] not in unit_dict[opener_ranked[0][0]]['MMs']:
                                    unit_dict[opener_ranked[0][0]]['MMs'][player["legion"]] = {'Count': 1, 'Wins': 0}
                                else:
                                    unit_dict[opener_ranked[0][0]]['MMs'][player["legion"]]['Count'] += 1
                                if player["spell"] not in unit_dict[opener_ranked[0][0]]['Spells']:
                                    unit_dict[opener_ranked[0][0]]['Spells'][player["spell"]] = {'Count': 1, 'Wins': 0}
                                else:
                                    unit_dict[opener_ranked[0][0]]['Spells'][player["spell"]]['Count'] += 1
                                unit_dict[opener_ranked[0][0]]['Worker'] += player["workers_per_wave"][3]
                                unit_dict[opener_ranked[0][0]]['Elo'] += player["player_elo"]
                                if player["game_result"] == 'won':
                                    unit_dict[opener_ranked[0][0]]['Wins'] += 1
                                    unit_dict[opener_ranked[0][0]]['MMs'][player["legion"]]['Wins'] += 1
                                    unit_dict[opener_ranked[0][0]]['Spells'][player["spell"]]['Wins'] += 1
                        except IndexError:
                            continue
                        except KeyError:
                            continue
        else:
            counter = 0
            for player in game["players_data"]:
                s = set()
                try:
                    for x in range(counter, counter+4):
                        for y in opener_ranked[x]:
                            s.add(y)
                except IndexError:
                    continue
                for y in s:
                    try:
                        opener_set = set(opener_ranked[counter])
                        if y not in opener_ranked[counter]:
                            for opener in opener_set:
                                if y in unit_dict[opener]['OpenWith']:
                                    unit_dict[opener]['OpenWith'][y]['Count'] += 1
                                    if player["game_result"] == 'won':
                                        unit_dict[opener]['OpenWith'][y]['Wins'] += 1
                                else:
                                    unit_dict[opener]['OpenWith'][y] = {'Count': 1, 'Wins': 0}
                                    if player["game_result"] == 'won':
                                        unit_dict[opener]['OpenWith'][y]['Wins'] += 1
                        else:
                            unit_dict[y]['Count'] += 1
                            if player["legion"] not in unit_dict[y]['MMs']:
                                unit_dict[y]['MMs'][player["legion"]] = {'Count': 1,'Wins': 0}
                            else:
                                unit_dict[y]['MMs'][player["legion"]]['Count'] += 1
                            if player["spell"] not in unit_dict[y]['Spells']:
                                unit_dict[y]['Spells'][player["spell"]] = {'Count': 1, 'Wins': 0}
                            else:
                                unit_dict[y]['Spells'][player["spell"]]['Count'] += 1
                            unit_dict[y]['Worker'] += player["workers_per_wave"][3]
                            unit_dict[y]['Elo'] += player["player_elo"]
                            if player["game_result"] == 'won':
                                unit_dict[y]['Wins'] += 1
                                unit_dict[y]['MMs'][player["legion"]]['Wins'] += 1
                                unit_dict[y]['Spells'][player["spell"]]['Wins'] += 1
                            for opener in opener_set:
                                if opener != y:
                                    if opener in unit_dict[y]['OpenWith']:
                                        unit_dict[y]['OpenWith'][opener]['Count'] += 1
                                        if player["game_result"] == 'won':
                                            unit_dict[y]['OpenWith'][opener]['Wins'] += 1
                                    else:
                                        unit_dict[y]['OpenWith'][opener] = {'Count': 1, 'Wins': 0}
                                        if player["game_result"] == 'won':
                                            unit_dict[y]['OpenWith'][opener]['Wins'] += 1
                    except IndexError:
                        continue
                    except KeyError:
                        continue
                counter += 4
    new_patches = []
    for x in patches:
        string = x
        periods = string.count('.')
        new_patches.append(string.split('.', periods)[0].replace('v', '') + '.' + string.split('.', periods)[1])
    patches = list(dict.fromkeys(new_patches))
    patches = sorted(patches, key=lambda x: int(x.split(".")[0] + x.split(".")[1]), reverse=True)
    newIndex = sorted(unit_dict, key=lambda x: unit_dict[x]['Count'], reverse=True)
    unit_dict = {k: unit_dict[k] for k in newIndex}
    avgelo = round(sum(gameelo_list)/len(gameelo_list))
    if data_only:
        return [unit_dict, games, avgelo]