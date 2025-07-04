import json
import math
import re
import time
import traceback
from datetime import datetime
from re import findall

modes = [
    'Super Fiesta',     # classic_special_mode_0
    'Giga Mercs',       # classic_special_mode_6
    'Superhero',        # classic_special_mode_8
    'Mini and Wumbo',   # classic_special_mode_9
    'PvE',              # classic_special_mode_11

    'Super Fiesta',     # classic_special_mode_0
    'Giga Mercs',       # classic_special_mode_6
    'Superhero',        # classic_special_mode_8
    'Mini and Wumbo',   # classic_special_mode_9
    'PvE',              # classic_special_mode_11

    'Super Fiesta',     # classic_special_mode_0
    'Giga Mercs',       # classic_special_mode_6
    'Superhero',        # classic_special_mode_8
    'Mini and Wumbo',   # classic_special_mode_9
    'Tower Defense',    # classic_special_mode_10
    'PvE'               # classic_special_mode_11
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


tier_dict_specific = {
    "mmstats": 1, "openstats": 1,
    "spellstats": 1, "unitstats": 1,
    "rollstats": 1, "megamindstats": 0,
    "matchupstats": 1
}

tier_dict_all = {
    "mmstats": 0.5, "openstats": 0.7,
    "spellstats": 0.4, "unitstats": 0.2,
    "rollstats": 0.3, "megamindstats": 0,
    "matchupstats": 1
}

elo_dict = {"2800": 0, "2600": 0.01, "2400": 0.02, "2200": 0.03, "2000": 0.05, "1800": 0.1, "1600": 0.15}

def get_tier_score(winrate, pickrate, dict_type, specific_tier, elo, stats):
    tier_dict = tier_dict_specific if dict_type else tier_dict_all
    try:
        if "-" in elo:
            elo = elo.split("-")[0]
    except TypeError:
        pass
    elo = elo_dict.get(str(elo), 0.04)

    if stats == "megamindstats" and not specific_tier:
        tier_score = winrate
    else:
        tier_score = winrate * (elo * 2 + 1) + pickrate * (tier_dict[stats] - elo)
        tier_score *= min(1, pickrate / (1 + pickrate))

    return tier_score

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
             | "openstats" | "Roll" | "Rolls" | "rollstats" | "Best Send" | "Best Roll" | "Sends" | "Best Unit" | "Champions":
            if string == "Save":
                return "/static/save.png"
            if not string and profile:
                return f"https://cdn.legiontd2.com/icons/Worker.png"
            return f"https://cdn.legiontd2.com/icons/{get_unit_name(string)}.png"
        case "MM" | "MMs" | "Best MMs" | "mmstats" | "megamindstats" | "Best With" | "Best Against" | "Teammate"\
            | "Enemies" | "Sending To" | "Receiving From" | "Match Up":
            if (string not in mm_list) and (string != "Hybrid"):
                return f"https://cdn.legiontd2.com/icons/{string}.png"
            else:
                return f"https://cdn.legiontd2.com/icons/Items/{string}.png"
        case "Spell" | "Spells" | "Best Spells" | "Best Spell" | "spellstats":
            return f"https://cdn.legiontd2.com/icons/{get_unit_name(string).replace('PresstheAttack', 'PressTheAttack').replace('None', 'Granddaddy')}.png"
        case "Wave" | "wavestats":
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
  
def get_key_value(data, key, k, games, stats="", elo = 0, specific_tier = False, dict_type = None, playerprofile = False, data_dict = {}, specific_key = "", main_key = ""):
    match k:
        case "Games":
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
        case "Pickrate" | "Playrate" | "Usage Rate" | "Pickrate*" | "Rollrate":
            try:
                if stats != "spellstats" or (specific_tier == True and stats == "spellstats") or key == "taxed allowance":
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
                return f"{get_synergy_counter_effect(main_key, data_dict, "Enemies", specific_key, False)}%"
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
    avg_end = wave_total/wave_count
    avg_end2 = round((avg_end-10), 1)
    def divide(x, y):
        try:
            return round(x / y * 100)
        except ZeroDivisionError:
            return 0
    return {"1-10": f"{round(10 * (1 - (pre10send_count / pre10_count)), 1)}/10 ({round((10 * (1 - (pre10send_count / pre10_count)))/10*100, 1)}%)",
            "11+": f"{round((avg_end - 10) * (1 - (send_count / count)), 1)}/{avg_end2} ({round((avg_end2 * (1 - (send_count / count)))/avg_end2*100, 1)}%)",
            "avg_end": f"{round(avg_end, 1)}", "pre10_myth_ratio": f"{divide(pre10_ratio[0], pre10_mythium)}% / {divide(pre10_ratio[1], pre10_mythium)}%",
            "post10_myth_ratio": f"{divide(post10_ratio[0], post10_mythium)}% / {divide(post10_ratio[1], post10_mythium)}%", "pre10_myth": round(pre10_mythium / games),
            "post10_myth": round(post10_mythium / games), "workers": avg_worker_per_wave, "leaks": avg_leak_per_wave, "income": avg_income_per_wave, "value": avg_value_per_wave}

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
            leak_amount += incmercs.get(x) / 20 * 4
        elif x in powermercs:
            if x == "Imp":
                leak_amount += powermercs.get(x) / 20 * 3
            else:
                leak_amount += powermercs.get(x) / 20 * 6
    if return_gold:
        return leak_amount
    else:
        return round(leak_amount / wave_total * 100, 1)
        
def get_value_playfab(list_of_dicts, value, version=9):
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