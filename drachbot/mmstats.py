import json
import drachbot.legion_api as legion_api
import util

def get_roll(unit_dict, unit_name):
    if unit_name == "kingpin":
        unit_name = "angler"
    elif unit_name == "sakura":
        unit_name = "seedling"
    elif unit_name == "iron maiden":
        unit_name = "cursed casket"
    elif unit_name == "hell raiser":
        unit_name = "masked spirit"
    elif unit_name == "hydra":
        unit_name = "eggsack"
    elif unit_name == "oathbreaker final form":
        unit_name = "chained fist"
    elif unit_name == "nucleus":
        unit_name = "proton"
    elif unit_dict[unit_name]["upgradesFrom"]:
        unit_name = unit_dict[unit_name]["upgradesFrom"]
    return unit_name

def mmstats(playerid, games, min_elo, patch, mastermind = 'All', sort="date", data_only = False, transparent = False, history_raw = {}):
    if mastermind == 'All':
        mmnames_list = util.mm_list
    elif mastermind == 'Megamind':
        mmnames_list = util.mm_list[:]
        mmnames_list.remove("Megamind")
    elif mastermind == 'Combined':
        mmnames_list = util.mm_list[:]
        mmnames_list.remove("Megamind")
    else:
        mmnames_list = [mastermind]
    masterminds_dict = {}
    for x in mmnames_list:
        masterminds_dict[x] = {"Count": 0, "Wins": 0, "Worker": 0, "Opener": {}, "Spell": {}, "Elo": 0, "Targets": {}, "Rolls": {}}
    unit_dict = {}
    with open('Files/json/units.json', 'r') as f:
        units_json = json.load(f)
    for u_js in units_json:
        if u_js["totalValue"] != '':
            string = u_js["unitId"]
            string = string.replace('_', ' ')
            string = string.replace(' unit id', '')
            if u_js["upgradesFrom"]:
                string2 = u_js["upgradesFrom"][0]
                string2 = string2.replace('_', ' ').replace(' unit id', '').replace('units ', '')
            else:
                string2 = ""
            unit_dict[string] = {'Count': 0, 'Wins': 0, 'Elo': 0, 'ComboUnit': {}, 'MMs': {}, 'Spells': {}, "upgradesFrom": string2}
    gameelo_list = []
    if type(history_raw) == str:
        return history_raw
    if len(history_raw) == 0:
        return 'No games found.'
    games = len(history_raw)
    case_list = util.mm_list
    patches = set()
    megamind_count = 0
    for game in history_raw:
        if (game["version"].startswith('v10') or game["version"].startswith('v9')) and (mastermind == 'Megamind' or mastermind == 'Champion'):
            continue
        patches.add(game["version"])
        gameelo_list.append(game["game_elo"])
        match mastermind:
            case 'All' | 'Megamind' | 'Combined':
                for player in game["players_data"]:
                    if player["player_id"] == playerid or playerid == "all":
                        if game["version"].startswith('v10') or game["version"].startswith('v9'):
                            player["megamind"] = False
                        if player["megamind"]:
                            megamind_count += 1
                            if mastermind == "Megamind":
                                if player["legion"] == "Megamind": continue
                                mastermind_current = player["legion"]
                            elif mastermind == "Combined":
                                # For combined stats, assign megamind games to the actual mastermind that was picked
                                if player["legion"] == "Megamind": continue
                                mastermind_current = player["legion"]
                            else:
                                mastermind_current = 'Megamind'
                        else:
                            if player["legion"] == "Mastermind":
                                continue
                            if mastermind == "Megamind":
                                continue
                            mastermind_current = player["legion"]
                        if mastermind_current not in masterminds_dict:
                            continue
                        masterminds_dict[mastermind_current]["Count"] += 1
                        if player["game_result"] == 'won':
                            masterminds_dict[mastermind_current]["Wins"] += 1
                        try:
                            masterminds_dict[mastermind_current]["Worker"] += player["workers_per_wave"][9]
                        except IndexError:
                            pass
                        masterminds_dict[mastermind_current]['Elo'] += player["player_elo"]
                        if ',' in player["opener"]:
                            string = player["opener"]
                            opener_list = set(string.split(','))
                        else:
                            opener_list = [player["opener"]]
                        if player["spell"] not in masterminds_dict[mastermind_current]['Spell']:
                            masterminds_dict[mastermind_current]['Spell'][player["spell"]] = {"Count": 1, "Wins": 0}
                            if player["game_result"] == 'won':
                                masterminds_dict[mastermind_current]['Spell'][player["spell"]]["Wins"] += 1
                        else:
                            masterminds_dict[mastermind_current]['Spell'][player["spell"]]["Count"] += 1
                            if player["game_result"] == 'won':
                                masterminds_dict[mastermind_current]['Spell'][player["spell"]]["Wins"] += 1
                        for opener in opener_list:
                            if opener not in masterminds_dict[mastermind_current]['Opener']:
                                masterminds_dict[mastermind_current]['Opener'][opener] = {"Count": 1, "Wins": 0}
                                if player["game_result"] == 'won':
                                    masterminds_dict[mastermind_current]['Opener'][opener]["Wins"] += 1
                            else:
                                masterminds_dict[mastermind_current]['Opener'][opener]["Count"] += 1
                                if player["game_result"] == 'won':
                                    masterminds_dict[mastermind_current]['Opener'][opener]["Wins"] += 1
                        if player["legion"] == "Champion":
                            champ_loc = player["champ_location"].split("|")
                            try:
                                champ_loc = (float(champ_loc[0]), float(champ_loc[1]))
                            except Exception:
                                continue
                        else:
                            champ_loc = None
                        for unit in player["build_per_wave"][-1].split("!"):
                            try:
                                unit_loc = unit.split(":")[1].split("|")
                            except IndexError:
                                continue
                            unit_loc = (float(unit_loc[0]), float(unit_loc[1]))
                            unit_name = unit.split(":")[0].replace("_", " ").replace(" unit id", "")
                            if unit_name == "" or unit_name not in unit_dict:
                                continue
                            unit_name = get_roll(unit_dict, unit_name)
                            if unit_loc == champ_loc:
                                if unit_name in masterminds_dict["Champion"]["Targets"]:
                                    masterminds_dict["Champion"]["Targets"][unit_name]["Count"] += 1
                                else:
                                    masterminds_dict["Champion"]["Targets"][unit_name] = {"Count": 1, "Wins": 0}
                                if player["game_result"] == "won":
                                    masterminds_dict["Champion"]["Targets"][unit_name]["Wins"] += 1
                        fighter_set = set()
                        for unit2 in player["build_per_wave"][-1].split("!"):
                            unit_name2 = unit2.split(":")[0].replace("_", " ").replace(" unit id", "")
                            if unit_name2 == "" or unit_name2 not in unit_dict:
                                continue
                            unit_name2 = get_roll(unit_dict, unit_name2)
                            fighter_set.add(unit_name2)
                        for fighter in fighter_set:
                            if fighter in masterminds_dict[mastermind_current]["Rolls"]:
                                masterminds_dict[mastermind_current]["Rolls"][fighter]["Count"] += 1
                            else:
                                masterminds_dict[mastermind_current]["Rolls"][fighter] = {"Count": 1, "Wins": 0}
                            if player["game_result"] == "won":
                                masterminds_dict[mastermind_current]["Rolls"][fighter]["Wins"] += 1
            case mastermind if mastermind in case_list:
                for player in game["players_data"]:
                    if (playerid == 'all' or player["player_id"] == playerid) and (mastermind == player["legion"]):
                        mastermind_current = player["legion"]
                        masterminds_dict[mastermind_current]["Count"] += 1
                        if player["game_result"] == 'won':
                            masterminds_dict[mastermind_current]["Wins"] += 1
                        try:
                            masterminds_dict[mastermind_current]["Worker"] += player["workers_per_wave"][9]
                        except IndexError:
                            pass
                        masterminds_dict[mastermind_current]['Elo'] += player["player_elo"]
                        if ',' in player["opener"]:
                            string = player["opener"]
                            opener_list = set(string.split(','))
                        else:
                            opener_list = [player["opener"]]
                        if player["spell"] not in masterminds_dict[mastermind_current]['Spell']:
                            masterminds_dict[mastermind_current]['Spell'][player["spell"]] = {"Count": 1, "Wins": 0}
                            if player["game_result"] == 'won':
                                masterminds_dict[mastermind_current]['Spell'][player["spell"]]["Wins"] += 1
                        else:
                            masterminds_dict[mastermind_current]['Spell'][player["spell"]]["Count"] += 1
                            if player["game_result"] == 'won':
                                masterminds_dict[mastermind_current]['Spell'][player["spell"]]["Wins"] += 1
                        for opener in opener_list:
                            if opener not in masterminds_dict[mastermind_current]['Opener']:
                                masterminds_dict[mastermind_current]['Opener'][opener] = {"Count": 1, "Wins": 0}
                                if player["game_result"] == 'won':
                                    masterminds_dict[mastermind_current]['Opener'][opener]["Wins"] += 1
                            else:
                                masterminds_dict[mastermind_current]['Opener'][opener]["Count"] += 1
                                if player["game_result"] == 'won':
                                    masterminds_dict[mastermind_current]['Opener'][opener]["Wins"] += 1
                        if player["legion"] == "Champion":
                            champ_loc = player["champ_location"].split("|")
                            try:
                                champ_loc = (float(champ_loc[0]), float(champ_loc[1]))
                            except Exception:
                                continue
                        else:
                            champ_loc = None
                        for unit in player["build_per_wave"][-1].split("!"):
                            try:
                                unit_loc = unit.split(":")[1].split("|")
                            except IndexError:
                                continue
                            unit_loc = (float(unit_loc[0]), float(unit_loc[1]))
                            unit_name = unit.split(":")[0].replace("_", " ").replace(" unit id", "")
                            if unit_name == "" or unit_name not in unit_dict:
                                continue
                            unit_name = get_roll(unit_dict, unit_name)
                            if unit_loc == champ_loc:
                                if unit_name in masterminds_dict["Champion"]["Targets"]:
                                    masterminds_dict["Champion"]["Targets"][unit_name]["Count"] += 1
                                else:
                                    masterminds_dict["Champion"]["Targets"][unit_name] = {"Count": 1, "Wins": 0}
                                if player["game_result"] == "won":
                                    masterminds_dict["Champion"]["Targets"][unit_name]["Wins"] += 1
                        fighter_set = set()
                        for unit2 in player["build_per_wave"][-1].split("!"):
                            unit_name2 = unit2.split(":")[0].replace("_", " ").replace(" unit id", "")
                            if unit_name2 == "" or unit_name2 not in unit_dict:
                                continue
                            unit_name2 = get_roll(unit_dict, unit_name2)
                            fighter_set.add(unit_name2)
                        for fighter in fighter_set:
                            if fighter in masterminds_dict[mastermind_current]["Rolls"]:
                                masterminds_dict[mastermind_current]["Rolls"][fighter]["Count"] += 1
                            else:
                                masterminds_dict[mastermind_current]["Rolls"][fighter] = {"Count": 1, "Wins": 0}
                            if player["game_result"] == "won":
                                masterminds_dict[mastermind_current]["Rolls"][fighter]["Wins"] += 1
    new_patches = []
    for x in patches:
        string = x
        periods = string.count('.')
        new_patches.append(string.split('.', periods)[0].replace('v', '') + '.' + string.split('.', periods)[1])
    patches = list(dict.fromkeys(new_patches))
    patches = sorted(patches, key=lambda x: int(x.split(".")[0] + x.split(".")[1]), reverse=True)
    newIndex = sorted(masterminds_dict, key=lambda x: masterminds_dict[x]['Count'], reverse=True)
    masterminds_dict = {k: masterminds_dict[k] for k in newIndex}
    avg_gameelo = round(sum(gameelo_list)/len(gameelo_list))
    if data_only:
        if mastermind == "Megamind":
            return [masterminds_dict, megamind_count, avg_gameelo]
        elif mastermind == "Combined":
            return [masterminds_dict, games, avg_gameelo]
        else:
            return [masterminds_dict, games, avg_gameelo]
