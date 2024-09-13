import json
import difflib
import util
import drachbot.legion_api as legion_api


def unitstats(playerid, games, min_elo, patch, sort="date", unit = "all", min_cost = 0, max_cost = 2000, data_only = False, transparent = False, rollstats = False, history_raw = {}):
    unit_dict = {}
    unit = unit.lower()
    with open('Files/json/units.json', 'r') as f:
        units_json = json.load(f)
    for u_js in units_json:
        if u_js["totalValue"] != '':
            if u_js["unitId"] and min_cost <= int(u_js["totalValue"]) <= max_cost: #and (u_js["sortOrder"].split(".")[1].endswith("U") or u_js["sortOrder"].split(".")[1].endswith("U2") or "neko" in u_js["unitId"]):
                string = u_js["unitId"]
                string = string.replace('_', ' ')
                string = string.replace(' unit id', '')
                if u_js["upgradesFrom"]:
                    string2 = u_js["upgradesFrom"][0]
                    string2 = string2.replace('_', ' ').replace(' unit id', '').replace('units ', '')
                else:
                    string2 = ""
                unit_dict[string] = {'Count': 0, 'Wins': 0, 'Elo': 0, 'ComboUnit': {}, 'MMs': {}, 'Spells': {}, "upgradesFrom": string2}
    if min_cost <= 75:
        unit_dict['pack rat (footprints)'] = {'Count': 0, 'Wins': 0, 'Elo': 0, 'ComboUnit': {}, 'MMs': {}, 'Spells': {}, "upgradesFrom": "looter"}
    if not unit_dict:
        return "No units found"
    if unit != "all":
        if unit in util.slang:
            unit = util.slang.get(unit)
        if unit not in unit_dict:
            close_matches = difflib.get_close_matches(unit, list(unit_dict.keys()))
            if len(close_matches) > 0:
                unit = close_matches[0]
            else:
                return unit + " unit not found."
    if type(history_raw) == str:
        return history_raw
    if len(history_raw) == 0:
        return 'No games found.'
    games = len(history_raw)
    patches = []
    gameelo_list = []
    for game in history_raw:
        patches.append(game["version"])
        gameelo_list.append(game["game_elo"])
        for player in game["players_data"]:
            if player["player_id"] != playerid and playerid != "all": continue
            fighter_set = set(player["fighters"].lower().split(","))
            fighter_set_copy = set(player["fighters"].lower().split(","))
            if rollstats:
                for fighter in fighter_set_copy:
                    if fighter == "" or fighter not in unit_dict:
                        continue
                    if fighter == "kingpin":
                        fighter_set.add("angler")
                        fighter_set.remove(fighter)
                    elif fighter == "sakura":
                        fighter_set.add("seedling")
                        fighter_set.remove(fighter)
                    elif fighter == "iron maiden":
                        fighter_set.add("cursed casket")
                        fighter_set.remove(fighter)
                    elif fighter == "hell raiser":
                        fighter_set.add("masked spirit")
                        fighter_set.remove(fighter)
                    elif fighter == "hydra":
                        fighter_set.add("eggsack")
                        fighter_set.remove(fighter)
                    elif fighter == "oathbreaker final form":
                        fighter_set.add("chained fist")
                        fighter_set.remove(fighter)
                    elif unit_dict[fighter]["upgradesFrom"]:
                        fighter_set.add(unit_dict[fighter]["upgradesFrom"])
                        fighter_set.remove(fighter)
            for fighter in fighter_set:
                if fighter == "" or fighter not in unit_dict:
                    continue
                unit_dict[fighter]["Count"] += 1
                unit_dict[fighter]["Elo"] += player["player_elo"]
                if player["spell"] in unit_dict[fighter]["Spells"]:
                    unit_dict[fighter]["Spells"][player["spell"]]["Count"] += 1
                else:
                    unit_dict[fighter]["Spells"][player["spell"]] = {"Count": 1, "Wins": 0}
                if player["legion"] in unit_dict[fighter]["MMs"]:
                    unit_dict[fighter]["MMs"][player["legion"]]["Count"] += 1
                else:
                    unit_dict[fighter]["MMs"][player["legion"]] = {"Count": 1, "Wins": 0}
                if player["game_result"] == "won":
                    unit_dict[fighter]["Wins"] += 1
                    unit_dict[fighter]["MMs"][player["legion"]]["Wins"] += 1
                    unit_dict[fighter]["Spells"][player["spell"]]["Wins"] += 1
                for combo_unit in fighter_set:
                    if combo_unit == fighter or combo_unit == unit_dict[fighter]["upgradesFrom"]: continue
                    if combo_unit in unit_dict[fighter]["ComboUnit"]:
                        unit_dict[fighter]["ComboUnit"][combo_unit]["Count"] += 1
                    else:
                        unit_dict[fighter]["ComboUnit"][combo_unit] = {"Count": 1, "Wins": 0}
                    if player["game_result"] == "won":
                        unit_dict[fighter]["ComboUnit"][combo_unit]["Wins"] += 1
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