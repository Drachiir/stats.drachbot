import platform
import json
import difflib
import util
import drachbot.legion_api as legion_api

shifts = [
    (-1.0, -0.5), (0.0, -1.0), (1.0, -0.5),
    (1.0, 0.5), (0.0, 1.0), (-1.0, 0.5),
    (0.5, -1.0), (1.0, 0.0), (0.5, 1.0),
    (-0.5, 1.0), (-1.0, 0.0), (-0.5, -1.0)
]

calculate_positions = lambda x, z: [(x, z)] + [(x + dx, z + dz) for dx, dz in shifts]

if platform.system() == "Linux":
    shared_folder = "/shared/Images/"
    shared2_folder = "/shared2/"
else:
    shared_folder = "shared/Images/"
    shared2_folder = "shared2/"

def spellstats(playerid, games, min_elo, patch, sort="date", spellname = "all", data_only = False, transparent = False, history_raw = {}):
    spell_dict = {}
    spellname = spellname.lower()
    with open('Files/json/spells.json', 'r') as f:
        spells_json = json.load(f)
    for s_js in spells_json:
        string = s_js["_id"]
        string = string.replace('_', ' ')
        string = string.replace(' powerup id', '')
        string = string.replace(' spell damage', '')
        spell_dict[string] = {'Count': 0, 'Wins': 0, 'Worker': 0, 'Elo': 0, 'Offered': 0, 'Opener': {}, 'MMs': {}, 'Targets': {}}
    spell_dict["taxed allowance"] = {'Count': 0, 'Wins': 0, 'Worker': 0, 'Elo': 0, 'Offered': 0, 'Opener': {}, 'MMs': {}, 'Targets': {}}
    if spellname != "all":
        if spellname in util.slang:
            spellname = util.slang.get(spellname)
        if spellname not in spell_dict:
            close_matches = difflib.get_close_matches(spellname, list(spell_dict.keys()))
            if len(close_matches) > 0:
                spellname = close_matches[0]
            else:
                return spellname + " spell not found."
    if type(history_raw) == str:
        return history_raw
    if len(history_raw) == 0:
        return 'No games found.'
    games = len(history_raw)
    patches = []
    gameelo_list = []
    for game in history_raw:
        if game["ending_wave"] < 11:
            continue
        patches.append(game["version"])
        gameelo_list.append(game["game_elo"])
        for player in game["players_data"]:
            if (player["player_id"] == playerid) or (playerid.lower() == 'all' or 'nova cup' in playerid):
                for offered_spell in game["spell_choices"]:
                    spell_dict[offered_spell.replace('_', ' ').replace(' powerup id', '').replace(' spell damage', '')]["Offered"] += 1
                if spellname != "all" and player["spell"].lower() != spellname:
                    continue
                spell_name = player["spell"].lower()
                spell_dict[spell_name]["Count"] += 1
                spell_dict[spell_name]["Elo"] += player["player_elo"]
                spell_dict[spell_name]["Worker"] += player["workers_per_wave"][9]
                if player["spell_location"] != "-1|-1":
                    spell_loc = player["spell_location"].split("|")
                    spell_loc = (float(spell_loc[0]), float(spell_loc[1]))
                    if spell_name in util.aura_spells:
                        target_locations = calculate_positions(spell_loc[0], spell_loc[1])
                    else:
                        target_locations = [spell_loc]
                    excluded_units = []
                    for unit in player["build_per_wave"][-1].split("!"):
                        try:
                            unit_loc = unit.split(":")[1].split("|")
                        except IndexError:
                            continue
                        unit_loc = (float(unit_loc[0]), float(unit_loc[1]))
                        if unit_loc in target_locations:
                            unit_name = unit.split(":")[0].replace("_", " ").replace(" unit id", "")
                            if unit_name in excluded_units:
                                continue
                            excluded_units.append(unit_name)
                            if unit_name in spell_dict[spell_name]["Targets"]:
                                spell_dict[spell_name]["Targets"][unit_name]["Count"] += 1
                            else:
                                spell_dict[spell_name]["Targets"][unit_name] = {"Count": 1, "Wins": 0}
                            if player["game_result"] == "won":
                                spell_dict[spell_name]["Targets"][unit_name]["Wins"] += 1
                if player["game_result"] == "won":
                    spell_dict[spell_name]["Wins"] += 1
                if "," in player["opener"]:
                    opener_current_list = set(player["opener"].split(","))
                else:
                    opener_current_list = [player["opener"]]
                for opener_current in opener_current_list:
                    if opener_current in spell_dict[spell_name]["Opener"]:
                        spell_dict[spell_name]["Opener"][opener_current]["Count"] += 1
                        if player["game_result"] == "won":
                            spell_dict[spell_name]["Opener"][opener_current]["Wins"] += 1
                    else:
                        spell_dict[spell_name]["Opener"][opener_current] = {"Count": 1, "Wins": 0}
                        if player["game_result"] == "won":
                            spell_dict[spell_name]["Opener"][opener_current]["Wins"] += 1
                if player["legion"] in spell_dict[spell_name]["MMs"]:
                    spell_dict[spell_name]["MMs"][player["legion"]]["Count"] += 1
                    if player["game_result"] == "won":
                        spell_dict[spell_name]["MMs"][player["legion"]]["Wins"] += 1
                else:
                    spell_dict[spell_name]["MMs"][player["legion"]] = {"Count": 1, "Wins": 0}
                    if player["game_result"] == "won":
                        spell_dict[spell_name]["MMs"][player["legion"]]["Wins"] += 1
                
    new_patches = []
    for x in patches:
        string = x
        periods = string.count('.')
        new_patches.append(string.split('.', periods)[0].replace('v', '') + '.' + string.split('.', periods)[1])
    patches = list(dict.fromkeys(new_patches))
    patches = sorted(patches, key=lambda x: int(x.split(".")[0] + x.split(".")[1]), reverse=True)
    newIndex = sorted(spell_dict, key=lambda x: spell_dict[x]['Count'], reverse=True)
    spell_dict = {k: spell_dict[k] for k in newIndex}
    avgelo = round(sum(gameelo_list)/len(gameelo_list))
    if data_only:
        return [spell_dict, games, avgelo]