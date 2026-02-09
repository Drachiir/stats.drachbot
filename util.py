import json
import math
import random
import re
import time
import traceback
from datetime import datetime
from re import findall

modes = [
    'PvE',              # classic_special_mode_11
    'Super Fiesta',     # classic_special_mode_0
    'Superhero',        # classic_special_mode_8
    'PvE',              # classic_special_mode_11
    'Mini and Wumbo',   # classic_special_mode_9
    'PvE',              # classic_special_mode_11
    'Giga Mercs',       # classic_special_mode_6
    'PvE',              # classic_special_mode_11
    'Super Fiesta',     # classic_special_mode_0
    'Superhero',        # classic_special_mode_8
    'PvE',              # classic_special_mode_11
    'Mini and Wumbo',   # classic_special_mode_9
]


images = {"Super Fiesta": "0", "Giga Mercs": "6", "Superhero": "8", "Mini and Wumbo": "9",
          "Tower Defense": "10", "PvE": "11"}

wave_names= [
    "Crab",
    "Wale",
    "Hopper",
    "FlyingChicken",
    "Scorpion",
    "Rocko",
    "Sludge",
    "Kobra",
    "Carapace",
    "Granddaddy",
    "QuillShooter",
    "Mantis",
    "DrillGolem",
    "KillerSlug",
    "Quadrapus",
    "Cardinal",
    "MetalDragon",
    "WaleChief",
    "DireToad",
    "Maccabeus",
    "LegionLord"
]

with open("Files/json/slang.json", "r") as f:
    slang = json.load(f)
    f.close()
    
with open("Files/json/const.json", "r") as f:
    const_file = json.load(f)
    f.close()

with open("Files/json/clankers.json", "r") as f:
    clankers = json.load(f)
    f.close()

with open("static/countries.json", "r") as f:
    COUNTRIES_CACHE = json.load(f)

with open("defaults.json", "r") as f:
    defaults_json = json.load(f)
    f.close()

incmercs = const_file.get("incmercs")
powermercs = const_file.get("powermercs")
creep_values = const_file.get("creep_values")
wave_values = const_file.get("wave_values")
rank_emotes = const_file.get("rank_emotes")
wave_emotes = const_file.get("wave_emotes")
mm_emotes = const_file.get("mm_emotes")

aura_spells = ["hero", "magician", "vampire"]
buff_spells = ["hero", "magician", "vampire", "divine blessing", "glacial touch", "guardian angel", "protector", "pulverizer", "sorcerer", "titan", "villain", "executioner"]

mm_list: list = defaults_json["MMs"]
mm_list.remove("All")

def patch_sort_key(patch_str):
    """
    Returns a tuple for sorting patch versions like '26.1', '26.1c', '26.2'.
    Handles letter suffixes in minor version (e.g., '1c' -> (1, 'c')).
    """
    parts = patch_str.split(".")
    major = int(parts[0])
    minor_str = parts[1] if len(parts) > 1 else "0"
    # Extract numeric part and optional letter suffix
    match = re.match(r'^(\d+)([a-zA-Z]*)$', minor_str)
    if match:
        minor_num = int(match.group(1))
        suffix = match.group(2)
    else:
        minor_num = 0
        suffix = minor_str
    return (major, minor_num, suffix)

def plus_prefix(a):
    if a > 0:
        b = '+' + str(a)
    else:
        b = str(a)
    return b

def get_avatar_border(stacks):
    if stacks >= 40:
        return f"static/ruby_64.png"
    elif stacks >= 20:
        return f"static/platinum_64.png"
    elif stacks >= 10:
        return f"static/gold_64.png"
    elif stacks >= 3:
        return f"static/silver_64.png"
    else:
        return ""


import math

# --- Main Configuration Dictionary ---
# All tuning and "magic numbers" are here for easy adjustment.
CONFIG = {
    # 1. Elo normalization map. Converts Elo string to a 0.0 (low) to 1.0 (high) factor.
    "elo_map": {
        "1600": 0.0,
        "1800": 0.2,
        "2000": 0.4,
        "2200": 0.6,
        "2400": 0.8,
        "2600": 0.9,
        "2800": 1.0,
        "default": 0.5  # Fallback for any unknown elo string
    },

    # 2. Base pick rate weights (for high elo, elo_factor = 1.0).
    # This defines the "base importance" of pick rate for each stat category.
    "stat_pr_weights_all": {
        "mmstats": 0.25, "mmstats_combined": 0.5, "openstats": 0.25,
        "spellstats": 0.4, "unitstats": 0.2,
        "rollstats": 0.3, "megamindstats": 0,
        "matchupstats": 1.0, "sendstats": 1.0
    },

    # Weights for the "specific" view (when dict_type is True)
    "stat_pr_weights_specific": {
        "mmstats": 1.0, "mmstats_combined": 1.0, "openstats": 1.0,
        "spellstats": 1.0, "unitstats": 1.0,
        "rollstats": 1.0, "megamindstats": 0,
        "matchupstats": 1.0, "sendstats": 1.0
    },

    # 3. Core Tuning Parameters

    # The "average" win rate. Scores are calculated relative to this.
    "avg_win_rate": 50.0,

    # --- Win Rate Weighting ---
    # At LOW elo (0.0), a 1% WR delta is this important.
    "wr_weight_low_elo": 1.5,
    # At HIGH elo (1.0), a 1% WR delta is this important.
    "wr_weight_high_elo": 1.0,

    # --- Pick Rate Weighting ---
    # At LOW elo (0.0), pick rate's importance is multiplied by this factor.
    # e.g., 0.5 = pick rate is half as important in low elo as it is in high elo.
    "pr_weight_low_elo_multiplier": 0.5,

    # --- Confidence Multiplier ---
    # This penalizes items with very low pick rates, just like your old code.
    # The formula is: pickrate / (pickrate + K)
    # K=1.0 matches your old code (pickrate / (pickrate + 1))
    # A higher K means you need a higher pickrate to get "full confidence".
    "pr_confidence_k": 3.0,  # At 3% PR, confidence is 0.5 (3 / (3+3))

    # --- Final Score Scaling ---
    # A final multiplier to get scores in a nice range (e.g., 0-100)
    "final_score_multiplier": 10.0
}


def lerp(a, b, t):
    """Linear interpolation: from a to b by factor t (0.0 to 1.0)"""
    return a * (1.0 - t) + b * t


def get_tier_score(winrate, pickrate, dict_type, specific_tier, elo, stats):
    """
    Calculates a tier score based on win rate and pick rate,
    with Elo-dependent weighting.
    """

    # --- 1. Handle Special Cases (from original code) ---
    # These stats just return the raw winrate, ignoring all logic.
    if (stats == "megamindstats" and not specific_tier) or \
            (stats == "mmstats_combined" and not specific_tier):
        return winrate

    # --- 2. Get Normalized Elo Factor (0.0 to 1.0) ---
    try:
        if "-" in elo:
            elo_key = elo.split("-")[0]
        else:
            elo_key = str(elo)
    except TypeError:
        elo_key = "default"

    elo_factor = CONFIG["elo_map"].get(elo_key, CONFIG["elo_map"]["default"])

    # --- 3. Get Base Stat PR Weight ---
    pr_weights_map = CONFIG["stat_pr_weights_specific"] if dict_type else CONFIG["stat_pr_weights_all"]
    base_pr_weight_high_elo = pr_weights_map.get(stats, 0.0)

    # --- 4. Calculate Elo-Adjusted Weights ---

    # Win Rate Weight:
    # Lerps from high weight (low elo) to lower weight (high elo).
    win_weight = lerp(CONFIG["wr_weight_low_elo"],
                      CONFIG["wr_weight_high_elo"],
                      elo_factor)

    # Pick Rate Weight:
    # Lerps from low weight (low elo) to high weight (high elo).
    pr_weight_low_elo = base_pr_weight_high_elo * CONFIG["pr_weight_low_elo_multiplier"]
    pick_weight = lerp(pr_weight_low_elo,
                       base_pr_weight_high_elo,
                       elo_factor)

    # --- 5. Calculate Core Score Components ---

    # Win Rate Component: (55% WR -> +5.0)
    wr_delta = winrate - CONFIG["avg_win_rate"]
    wr_score = wr_delta * win_weight

    # Pick Rate Component: (10% PR * 0.7 weight -> 7.0)
    pr_score = pickrate * pick_weight

    # Combine components
    core_score = wr_score + pr_score

    # --- 6. Apply Pick Rate Confidence ---
    # This penalizes the score if pick rate is very low.
    # (e.g., a 1% PR item with 90% WR is probably an anomaly).
    pr_confidence = pickrate / (pickrate + CONFIG["pr_confidence_k"])

    final_score = core_score * pr_confidence * CONFIG["final_score_multiplier"]

    if pickrate == 100:
        final_score /= 10

    return final_score


def custom_winrate(value, no_dec=False):
    try:
        if no_dec:
            return round(value[0] / value[1] * 100)
        else:
            return round(value[0] / value[1] * 100, 1)
    except Exception:
        return 0

def custom_divide(value, dec=0):
    try:
        return round(value[0] / value[1], dec)
    except Exception:
        return 0

def human_format(num):
    num = float('{:.3g}'.format(num))
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    return '{}{}'.format('{:f}'.format(num).rstrip('0').rstrip('.'), ['', 'K', 'M', 'B', 'T'][magnitude])

def get_perf_list(dict2, key, dict_type, specific_tier, elo, stats, profile=False):
    new_dict = {}
    for xy in dict2[key]:
        if xy == "none" or not xy: continue
        if xy == "Save": continue
        winrate = (dict2[key][xy]['Wins'] / dict2[key][xy]['Count'])*100
        pickrate = (dict2[key][xy]['Count'] / dict2['Count'])*100
        if key not in ["Mercs", "Units"]:
            if (winrate < dict2['Wins'] / dict2['Count'] * 100) and not profile:
                continue
            tier_score = get_tier_score(winrate, pickrate, dict_type, specific_tier, elo, stats)
            new_dict[xy] = tier_score
        else:
            if dict2[key][xy]['Count'] < (dict2['Count']*0.05):
                continue
            if xy == "Snail":
                new_dict[xy] = (winrate*50) + pickrate
            else:
                new_dict[xy] = (winrate*50) + (pickrate*10)
    newIndex = sorted(new_dict, key=lambda k: new_dict[k], reverse=True)
    return newIndex

def get_synergy_counter_effect(unit, dict1, key, unit2, synergy):
    overall_winrate = dict1[unit][key][unit2]["Wins"] / dict1[unit][key][unit2]["Count"]
    winrate_a = dict1[unit]["Wins"] / dict1[unit]["Count"]
    winrate_b = dict1[unit2]["Wins"] / dict1[unit2]["Count"]
    #print(unit, key, unit2, overall_winrate, winrate_a, winrate_b)

    if synergy:
        value = winrate_a * winrate_b / (winrate_a * winrate_b + (1 - winrate_a) * (1 - winrate_b))
    else:
        value = winrate_a * (1 - winrate_b) / (winrate_a * (1 - winrate_b) + (1 - winrate_a) * winrate_b)

    return round((overall_winrate - value) * 100, 1)

def get_synergy_counter_effect_list(unit, dict1, key, synergy):
    new_dict = {}
    for xy in dict1[unit][key]:
        try:
            tier_score = get_synergy_counter_effect(unit, dict1, key, xy, synergy)
        except Exception:
            continue
        new_dict[xy] = tier_score
    newIndex = sorted(new_dict, key=lambda k: new_dict[k], reverse=True)
    return newIndex

def get_dict_value(dict, value):
    try:
        return dict[value]
    except Exception:
        return {"Count": 0, "Wins": 0}

def sort_dict(dict, key):
    newIndex = sorted(dict, key=lambda x: dict[x][key], reverse=True)
    return {k: dict[k] for k in newIndex}


def get_unit_name(name):
    if not name:
        return ""
    if "_" in name:
        if "_unit_id" in name:
            name = name.split("_unit_id")[0]
            if name[0] == " ":
                name = name[1:]
        split_char = "_"
    else:
        split_char = " "
    new_string = ""
    for string in name.split(split_char):
        new_string += string.capitalize()
    if new_string == "HellRaiserBuffed":
        new_string = "HellRaiser"
    if new_string == "PackRat(footprints)":
        new_string = "PackRat(Footprints)"
    if new_string == "PackRatNest":
        new_string = "PackRat(Footprints)"
    if new_string == "Aps":
        new_string = "APS"
    if new_string == "Mps":
        new_string = "MPS"
    return new_string

def get_unit_name_list(name):
    if not name:
        return ""
    else:
        name = name[0]
    new_string = ""
    for string in name.split(" "):
        new_string += string.capitalize()
    if new_string == "HellRaiserBuffed":
        new_string = "HellRaiser"
    if new_string == "PackRat(footprints)":
        new_string = "PackRat(Footprints)"
    if new_string == "PackRatNest":
        new_string = "PackRat(Footprints)"
    if new_string == "Aps":
        new_string = "APS"
    if new_string == "Mps":
        new_string = "MPS"
    return new_string

def get_cdn_image(string, header, profile = False):
    match header:
        case "Opener" | "Openers" | "Best Opener" | "Adds" | "Best Add" | "Unit"\
             | "Best Combo" | "Combos" | "Targets" | "unitstats" | "Units"\
             | "openstats" | "Roll" | "Rolls" | "rollstats" | "Best Send" | "Best Roll" |\
             "Sends" | "Best Unit" | "Champions" | "Send" | "Best Into" | "Best With*" | "Combo":
            if string == "Save":
                return "/static/save.png"
            if not string and profile:
                return f"https://cdn.legiontd2.com/icons/Worker.png"
            return f"https://cdn.legiontd2.com/icons/{get_unit_name(string)}.png"
        case "MM" | "MMs" | "Best MMs" | "mmstats" | "mmstats_combined" | "megamindstats" | "Best With" | "Best Against" | "Teammate"\
            | "Enemies" | "Sending To" | "Receiving From" | "Match Up":
            if (string not in mm_list) and (string != "Hybrid"):
                return f"https://cdn.legiontd2.com/icons/{string}.png"
            else:
                return f"https://cdn.legiontd2.com/icons/Items/{string}.png"
        case "Spell" | "Spells" | "Best Spells" | "Best Spell" | "spellstats":
            return f"https://cdn.legiontd2.com/icons/{get_unit_name(string).replace('PresstheAttack', 'PressTheAttack').replace('None', 'Granddaddy')}.png"
        case "Wave" | "wavestats" | "Best Wave" | "Waves":
            wave_num = findall(r'\d+', string)
            return f"https://cdn.legiontd2.com/icons/{wave_names[int(wave_num[0])-1]}.png"

def get_tooltip(header:str):
    header = str(header)
    if header.startswith("Best"):
        if header == "Best Add":
            return f"Best Unit built within the first 4 waves based on Win% and Play%"
        elif header == "Best Send":
            return f"Best Send based on Win% and Send% on this wave"
        elif header == "Best Unit":
            return f"Best Unit based on Win% and Play% on this wave"
        elif header == "Best With":
            return f"Best Mastermind for Teammate"
        elif header == "Best Against":
            return f"Best against this Mastermind on Enemy team"
        return f"Best {header.split(" ")[1]} based on Win% and Play%"
    match header:
        case "Tier":
            return "Tier based on Win%, Play% and Elo"
        case "Usage Rate":
            return "% of time this Unit appears on End boards"
        case "Pickrate":
            return "Per Game Frequency e.g. 100% = 1 per Game"
        case "Pickrate*":
            return "% of time picked, when available"
        case "W on 4":
            return "Workers at the end of Wave 4"
        case "W on 10":
            return "Workers at the end of Wave 10"
        case "Best Add" | "Adds":
            return "Units added within the first 4 waves"
        case "MM":
            return "Mastermind"
        case "Champions":
            return  "Base Units with the Champion buff"
        case "Openers":
            return "Units built on Wave 1"
        case "Targets":
            return "Units affected by this buff"
        case "Synergy":
            return "Synergy Effect, higher = better"
        case "Counter":
            return "Counter Effect, higher = better"
        case "Delta":
            return "Winrate delta"
        case _:
            return header.capitalize()
  
def get_key_value(data, key, k, games, stats="", elo = 0, specific_tier = False, dict_type = None, playerprofile = False, data_dict = {}, specific_key = "", main_key = "", dict_header = None):
    match k:
        case "Games" | "Sends":
            try:
                return data[key]['Count']
            except Exception:
                return 0
        case "Winrate":
            try:
                return f"{custom_winrate([data[key]['Wins'], data[key]['Count']])}%"
            except Exception:
                return 0
        case "Delta":
            try:
                return custom_winrate([data[key]['Wins'], data[key]['Count']])
            except Exception:
                return 0
        case "Pickrate" | "Playrate" | "Usage Rate" | "Pickrate*" | "Rollrate" | "Sendrate*":
            try:
                if stats != "spellstats" or (specific_tier == True and stats == "spellstats") or key == "taxed allowance":
                    if stats == "sendstats" and not specific_key:
                        return f"{custom_winrate([data[key]['Count'], data[key]['WaveCount']])}%"
                    else:
                        return f"{custom_winrate([data[key]['Count'], games])}%"
                else:
                    return f"{custom_winrate([data[key]['Count'], data[key]['Offered']])}%"
            except Exception:
                return 0
        case "Synergy":
            try:
                return f"{get_synergy_counter_effect(main_key, data_dict, "Teammates", specific_key, True)}%"
            except Exception:
                return 0
        case "Counter":
            try:
                return f"{get_synergy_counter_effect(main_key, data_dict, dict_header, specific_key, False)}%"
            except Exception:
                return 0
        case "Player Elo":
            return int(custom_divide([data[key]['Elo'], data[key]['Count']]))
        case "W on 10":
            return custom_divide([data[key]['Worker'], data[key]['Count']], 1)
        case "W on 4":
            return custom_divide([data[key]['Worker'], data[key]['Count']], 1)
        case "Tier":
            try:
                winrate = custom_winrate([data[key]['Wins'], data[key]['Count']])
            except Exception:
                winrate = 0
            try:
                if stats != "spellstats" or (specific_tier == True and stats == "spellstats") or key == "taxed allowance":
                    pickrate = custom_winrate([data[key]['Count'], games])
                else:
                    pickrate = custom_winrate([data[key]['Count'], data[key]['Offered']])
            except Exception:
                pickrate = 0
            return get_tier_score(winrate, pickrate, dict_type, specific_tier, elo, stats)
        case "Best Opener":
            try:
                return get_perf_list(data[key], 'Opener', dict_type, specific_tier, elo, stats, profile=playerprofile)[0]
            except Exception:
                return 0
        case "Best Spell":
            try:
                return get_perf_list(data[key], 'Spells', dict_type, specific_tier, elo, stats, profile=playerprofile)[0]
            except KeyError:
                try:
                    return get_perf_list(data[key], 'Spell', dict_type, specific_tier, elo, stats, profile=playerprofile)[0]
                except Exception:
                    return 0
            except IndexError:
                return None
        case "Best Add":
            try:
                return get_perf_list(data[key], 'OpenWith', dict_type, specific_tier, elo, stats, profile=playerprofile)[0]
            except IndexError:
                return None
        case "Best Roll":
            try:
                return get_perf_list(data[key], 'Rolls', dict_type, specific_tier, elo, stats, profile=playerprofile)[0]
            except IndexError:
                return None
        case "Best Combo":
            try:
                return get_perf_list(data[key], 'ComboUnit', dict_type, specific_tier, elo, stats, profile=playerprofile)[0]
            except IndexError:
                return None
        case "Best Wave":
            try:
                return get_perf_list(data[key], 'Waves', dict_type, specific_tier, elo, stats, profile=playerprofile)[0]
            except IndexError:
                return None
        case "Best Into":
            try:
                return get_perf_list(data[key], 'Units', dict_type, specific_tier, elo, stats, profile=playerprofile)[0]
            except IndexError:
                return None
        case "Best With*":
            try:
                return get_perf_list(data[key], 'MercsCombo', dict_type, specific_tier, elo, stats, profile=playerprofile)[0]
            except IndexError:
                return None
        case "Best MMs":
            try:
                return get_perf_list(data[key], 'MMs', dict_type, specific_tier, elo, stats, profile=playerprofile)[0]
            except IndexError:
                return None
        case "Best Send":
            try:
                return get_perf_list(data[key], 'Mercs', dict_type, specific_tier, elo, stats, profile=playerprofile)[0]
            except IndexError:
                return None
        case "Best Unit":
            try:
                return get_perf_list(data[key], 'Units', dict_type, specific_tier, elo, stats, profile=playerprofile)[0]
            except IndexError:
                return None
        case "Best With":
            try:
                if playerprofile:
                    return get_perf_list(data[key], 'Teammates', dict_type, specific_tier, elo, stats, profile=playerprofile)[0]
                else:
                    return get_synergy_counter_effect_list(key, data, 'Teammates', True)[0]
            except Exception:
                return None
        case "Best Against":
            try:
                if playerprofile:
                    return get_perf_list(data[key], 'Enemies', dict_type, specific_tier, elo, stats, profile=playerprofile)[0]
                else:
                    return get_synergy_counter_effect_list(key, data, 'Enemies', False)[0]
            except Exception:
                return None
        case "Endrate":
            return f"{custom_winrate([data[key]['EndCount'], games])}%"
        case "Sendrate":
            if playerprofile:
                return f"{custom_winrate([data[key]['SendCount'], data[key]['Count']])}%"
            else:
                return f"{custom_winrate([data[key]['SendCount'] / 4, data[key]['Count']])}%"
        case "Avg Leak":
            wave_num = findall(r'\d+', key)
            if playerprofile:
                return f"{round(data[key]["LeakedGold"]/(wave_values[int(wave_num[0])-1]*(data[key]["Count"]))*100,1)}%"
            else:
                return f"{round(data[key]["LeakedGold"] / (wave_values[int(wave_num[0]) - 1] * (data[key]["Count"] * 4)) * 100, 1)}%"

def get_gamestats_values(data, games, playerprofile = False):
    pre10_count, pre10send_count = 0, 0
    count, send_count = 0, 0
    wave_total, wave_count = 0, 0
    pre10_mythium, post10_mythium = 0, 0
    pre10_ratio, post10_ratio = [0, 0], [0, 0]
    avg_leak_per_wave = []
    avg_worker_per_wave = []
    avg_income_per_wave = []
    avg_value_per_wave = []
    for i, wave in enumerate(data["WaveDict"]):
        wave_total += int(re.findall(r'\d+', wave)[0]) * data["WaveDict"][wave]["EndCount"]
        wave_count += data["WaveDict"][wave]["EndCount"]
        avg_leak_per_wave.append(round(data["WaveDict"][wave]["LeakedGold"] / (wave_values[i] * data["WaveDict"][wave]["Count"]) * 100 if wave_values[i] != 0 and data["WaveDict"][wave]["Count"] != 0 else 0, 1))
        avg_worker_per_wave.append(round(data["WaveDict"][wave]["Worker"] / data["WaveDict"][wave]["Count"] if data["WaveDict"][wave]["Count"] != 0 else 0, 1))
        avg_income_per_wave.append(round(data["WaveDict"][wave]["Income"] / data["WaveDict"][wave]["Count"] if data["WaveDict"][wave]["Count"] != 0 else 0, 1))
        avg_value_per_wave.append(round(data["WaveDict"][wave]["Value"] / data["WaveDict"][wave]["Count"] if data["WaveDict"][wave]["Count"] != 0 else 0, 1))
        if int(re.findall(r'\d+', wave)[0]) <= 10:
            pre10_count += data["WaveDict"][wave]["Count"]
            pre10send_count += data["WaveDict"][wave]["SendCount"]
            pre10_mythium += data["WaveDict"][wave]["IncomeMerc"] + data["WaveDict"][wave]["PowerMerc"]
            pre10_ratio[0] += data["WaveDict"][wave]["IncomeMerc"]
            pre10_ratio[1] += data["WaveDict"][wave]["PowerMerc"]
        if int(re.findall(r'\d+', wave)[0]) > 10:
            count += data["WaveDict"][wave]["Count"]
            send_count += data["WaveDict"][wave]["SendCount"]
            post10_mythium += data["WaveDict"][wave]["IncomeMerc"] + data["WaveDict"][wave]["PowerMerc"]
            post10_ratio[0] += data["WaveDict"][wave]["IncomeMerc"]
            post10_ratio[1] += data["WaveDict"][wave]["PowerMerc"]
    avg_end = (wave_total / wave_count) if wave_count else 0.0
    post_target = max(avg_end - 10.0, 0.0)  # waves after 10 we "expect"
    post_target_r = round(post_target, 1)

    def pct(x, y, ndigits=1):
        """Return x/y as percent (0..100)."""
        return round((x / y) * 100, ndigits) if y else 0.0

    def ratio(x, y):
        """Return x/y (0..1)."""
        return (x / y) if y else 0.0

    pre10_send_ratio = ratio(pre10send_count, pre10_count)  # fraction of pre10 waves with sends
    post_send_ratio = ratio(send_count, count)  # fraction of post10 waves with sends

    pre10_def = round(10.0 * (1.0 - pre10_send_ratio), 1)
    pre10_pct = round((1.0 - pre10_send_ratio) * 100.0, 1)

    post_def = round(post_target * (1.0 - post_send_ratio), 1)
    post_pct = round((1.0 - post_send_ratio) * 100.0, 1)

    return {
        "1-10": f"{pre10_def}/10 ({pre10_pct}%)",
        "11+": f"{post_def}/{post_target_r} ({post_pct}%)",
        "avg_end": f"{round(avg_end, 1)}",
        "pre10_myth_ratio": f"{pct(pre10_ratio[0], pre10_mythium, 0)}% / {pct(pre10_ratio[1], pre10_mythium, 0)}%",
        "post10_myth_ratio": f"{pct(post10_ratio[0], post10_mythium, 0)}% / {pct(post10_ratio[1], post10_mythium, 0)}%",
        "pre10_myth": round(pre10_mythium / games) if games else 0,
        "post10_myth": round(post10_mythium / games) if games else 0,
        "workers": avg_worker_per_wave,
        "leaks": avg_leak_per_wave,
        "income": avg_income_per_wave,
        "value": avg_value_per_wave,
    }


def time_ago(time=False):
    now = datetime.utcnow()
    if type(time) is int:
        diff = now - datetime.fromtimestamp(time)
    elif type(time) is float:
        diff = now - datetime.fromtimestamp(time)
    elif isinstance(time, datetime):
        diff = now - time
    elif not time:
        diff = now - now
    else:
        raise ValueError('invalid date %s of type %s' % (time, type(time)))
    second_diff = diff.seconds
    day_diff = diff.days
    if day_diff < 0:
        return ''

    if day_diff == 0:
        if second_diff < 10:
            return "just now"
        if second_diff < 60:
            return str(round(second_diff)) + " seconds ago"
        if second_diff < 120:
            return  "a minute ago"
        if second_diff < 3600:
            return str( round(second_diff / 60) ) + " minutes ago"
        if second_diff < 7200:
            return "an hour ago"
        if second_diff < 86400:
            return str( round(second_diff / 3600) ) + " hours ago"
    if day_diff == 1:
        return "Yesterday"
    if day_diff < 7:
        if day_diff == 1:
            temp = ""
        else:
            temp = "s"
        return str(round(day_diff)) + f" day{temp} ago"
    if day_diff < 31:
        if day_diff/7 >= 2:
            temp = "s"
        else:
            temp = ""
        return str(round(day_diff/7)) + f" week{temp} ago"
    if day_diff < 365:
        if day_diff/30 >= 2:
            temp = "s"
        else:
            temp = ""
        return str(round(day_diff/30)) + f" month{temp} ago"
    return str(round(day_diff/365)) + " years ago"

def get_rank_url(elo):
    try:
        elo = int(elo)
    except Exception:
        try:
            if type(elo) == str:
                if "-" in elo:
                    elo = int(elo.split("-")[0])
                else:
                    elo = int(elo.replace("+", ""))
            else:
                elo = int(elo)
        except Exception:
            elo = 0
    if elo >= 2800:
        rank_url = 'https://cdn.legiontd2.com/icons/Ranks/Simple/Legend.png'
    elif elo >= 2600:
        rank_url = 'https://cdn.legiontd2.com/icons/Ranks/Simple/GrandMaster.png'
    elif elo >= 2400:
        rank_url = 'https://cdn.legiontd2.com/icons/Ranks/Simple/SeniorMaster.png'
    elif elo >= 2200:
        rank_url = 'https://cdn.legiontd2.com/icons/Ranks/Simple/Master.png'
    elif elo >= 2000:
        rank_url = 'https://cdn.legiontd2.com/icons/Ranks/Simple/Expert.png'
    elif elo >= 1800:
        rank_url = 'https://cdn.legiontd2.com/icons/Ranks/Simple/Diamond.png'
    elif elo >= 1600:
        rank_url = 'https://cdn.legiontd2.com/icons/Ranks/Simple/Platinum.png'
    elif elo >= 1400:
        rank_url = 'https://cdn.legiontd2.com/icons/Ranks/Simple/Gold.png'
    elif elo >= 1200:
        rank_url = 'https://cdn.legiontd2.com/icons/Ranks/Simple/Silver.png'
    elif elo >= 1000:
        rank_url = 'https://cdn.legiontd2.com/icons/Ranks/Simple/Bronze.png'
    else:
        rank_url = 'https://cdn.legiontd2.com/icons/Ranks/Simple/Unranked.png'
    return rank_url

def get_avg_end_wave(data:dict) -> str:
    try:
        wave_total = 0
        count = 0
        for wave in data:
            wave_total += int(re.findall(r'\d+', wave)[0]) * data[wave]["EndCount"]
            count += data[wave]["EndCount"]
        return f"{round(wave_total/count, 1)}"
    except Exception:
        return ""

def count_mythium(send, seperate = False):
    if type(send) != type(list()):
        if send == "":
            send = []
        else:
            send = send.split("!")
    inc_amount = 0
    power_amount = 0
    for x in send:
        if "Upgrade" in x:
            continue
        if x in incmercs:
            inc_amount += incmercs.get(x)
        else:
            power_amount += powermercs.get(x)
    if seperate:
        return inc_amount, power_amount
    else:
        return inc_amount + power_amount

def calc_leak(leak, wave, return_gold = False):
    if type(leak) != type(list()):
        if leak == "":
            leak = []
        else:
            leak = leak.split("!")
    leak_amount = 0
    send_amount = 0
    wave_total = wave_values[wave]
    for x in leak:
        if x in creep_values:
            leak_amount += creep_values.get(x)[1]
        elif x in incmercs:
            leak_amount += incmercs.get(x) / 20 * 2
        elif x in powermercs:
            if x == "Imp":
                leak_amount += powermercs.get(x) / 20 * 1.5
            else:
                leak_amount += powermercs.get(x) / 20 * 3
    if return_gold:
        return leak_amount
    else:
        return round(leak_amount / wave_total * 100, 1)
        
def get_value_playfab(list_of_dicts, value, version=10):
    for x in list_of_dicts:
        if (x["Name"] == value) and (x["Version"] == version):
            return x["Value"]
    else:
        return 0
        
def clean_unit_name(name):
    return name.split("_unit_id")[0].replace("_", " ").capitalize()

def timing_decorator(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()  # Record start time
        result = func(*args, **kwargs)
        end_time = time.time()  # Record end time
        print(f"{func.__name__} took {end_time - start_time:.4f} seconds")
        return result
    return wrapper

def merge_dicts(target, source):
    """Recursively merge two dictionaries, summing up values for matching keys."""
    for key, value in source.items():
        if isinstance(value, dict):
            target[key] = merge_dicts(target.get(key, {}), value)
        else:
            if key == "Cost":
                continue
            try:
                target[key] = target.get(key, 0) + value
            except Exception:
                continue
    return target

def is_special_player(playerid):
    if playerid in clankers["clankers"]:
        return True
    else:
        return False

def generate_values(playerid, original_values):
    if playerid not in clankers["clankers"]:
        return original_values
    random.seed(hash(playerid))
    if len(original_values) < 2:
        return original_values
    
    fake_values = [original_values[0]]
    target_value = original_values[-1]
    start_value = original_values[0]
    
    for i in range(1, len(original_values) - 1):
        prev_value = fake_values[-1]
        remaining_steps = len(original_values) - i - 1
        
        change = random.randint(12, 22)
        if random.random() < 0.5:
            change = -change
        
        new_value = prev_value + change
        
        min_allowed = start_value - 200
        max_allowed = start_value + 200
        
        if new_value < min_allowed:
            new_value = min_allowed
        elif new_value > max_allowed:
            new_value = max_allowed
        
        if remaining_steps > 0:
            distance_to_target = abs(target_value - new_value)
            max_possible_change = remaining_steps * 22
            
            if distance_to_target > max_possible_change:
                if new_value > target_value:
                    new_value = target_value + max_possible_change
                else:
                    new_value = target_value - max_possible_change
        
        fake_values.append(new_value)
    
    fake_values.append(original_values[-1])
    return fake_values

def generate_stats(playerid,winlose,elochange,api_stats=None):
    if playerid not in clankers["clankers"]:return winlose,elochange,api_stats
    rng=random.Random(hash(playerid)+12345)
    def noisy_split(total,a,b):
        if a+b<=0:w_a=rng.gammavariate(1.2,1.0);w_b=rng.gammavariate(1.2,1.0)
        else:w_a=rng.gammavariate(max(0.8,a/max(1,a+b)*3),1.0);w_b=rng.gammavariate(max(0.8,b/max(1,a+b)*3),1.0)
        s=w_a+w_b;part_a=int(round(total*(w_a/s)));part_b=total-part_a;return part_a,part_b
    total_games_orig=winlose["Overall"][0]+winlose["Overall"][1]
    if total_games_orig>0:
        target_total=rng.randint(200,300) if total_games_orig>300 else total_games_orig
        wins=rng.randint(int(target_total*0.45),int(target_total*0.55));losses=target_total-wins
        solo_games_orig=winlose["SoloQ"][0]+winlose["SoloQ"][1];duo_games_orig=winlose["DuoQ"][0]+winlose["DuoQ"][1]
        solo_games,duo_games=noisy_split(target_total,solo_games_orig,duo_games_orig)
        solo_wins,duo_wins=noisy_split(wins,solo_games,duo_games)
        solo_wins=min(solo_wins,solo_games);duo_wins=min(duo_wins,duo_games)
        solo_losses=solo_games-solo_wins;duo_losses=duo_games-duo_wins
        winlose={"Overall":[solo_wins+duo_wins,solo_losses+duo_losses],"SoloQ":[solo_wins,solo_losses],"DuoQ":[duo_wins,duo_losses]}
    elochange={"Overall":rng.randint(-200,200),"SoloQ":rng.randint(-200,200),"DuoQ":rng.randint(-200,200)}
    if api_stats:
        season_wins=api_stats.get("rankedWinsThisSeason",0);season_losses=api_stats.get("rankedLossesThisSeason",0);season_total_orig=season_wins+season_losses
        if season_total_orig>0:
            season_total=rng.randint(200,300) if season_total_orig>300 else season_total_orig
            season_wins=rng.randint(int(season_total*0.45),int(season_total*0.55));season_losses=season_total-season_wins
            api_stats=api_stats.copy();api_stats["rankedWinsThisSeason"]=season_wins;api_stats["rankedLossesThisSeason"]=season_losses
    return winlose,elochange,api_stats