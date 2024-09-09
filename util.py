import re
from copyreg import pickle
from datetime import datetime
from re import findall

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

wave_values = [72, 84, 90, 96, 108, 114, 100, 132, 144, 150, 156, 168, 180, 192, 204, 216, 228, 252, 276, 300, 360]

def custom_winrate(value):
    try:
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

def get_perf_list(dict2, key):
    new_dict = {}
    for xy in dict2[key]:
        if xy == "none": continue
        if key not in ["Mercs", "Units"]:
            if dict2[key][xy]['Wins'] / dict2[key][xy]['Count'] < dict2['Wins'] / dict2['Count']:
                continue
            new_dict[xy] = dict2[key][xy]['Wins'] / dict2[key][xy]['Count'] * (dict2[key][xy]['Count'] / dict2['Count'])
        else:
            if dict2[key][xy]['Count'] < (dict2['Count']*0.05):
                continue
            if xy == "Snail":
                new_dict[xy] = ((dict2[key][xy]['Wins'] / dict2[key][xy]['Count'])*50) + (dict2[key][xy]['Count'] / dict2['Count'])
            else:
                new_dict[xy] = ((dict2[key][xy]['Wins'] / dict2[key][xy]['Count'])*50) + ((dict2[key][xy]['Count'] / dict2['Count'])*10)
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

def get_cdn_image(string, header):
    match header:
        case "Opener" | "Openers" | "Best Opener" | "Adds" | "Best Add" | "Unit"\
             | "Best Combo" | "Combos" | "Targets" | "unitstats" | "Units"\
             | "openstats" | "Roll" | "Rolls" | "rollstats" | "Best Merc" | "Best Roll" | "Mercs" | "Best Unit" | "Champions":
            return f"https://cdn.legiontd2.com/icons/{get_unit_name(string)}.png"
        case "MM" | "MMs" | "Best MMs" | "mmstats":
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
        elif header == "Best Merc":
            return f"Best Merc based on Win% and Send% on this wave"
        elif header == "Best Unit":
            return f"Best Unit based on Win% and Play% on this wave"
        return f"Best {header.split(" ")[1]} based on Win% and Play%"
    match header:
        case "Tier":
            return "Tier based on Win% and Play% EXPERIMENTAL"
        case "Usage Rate":
            return "% of time this Unit appears on End boards"
        case "Pickrate":
            return "Per Game Frequency e.g. 100% = 1 per Game"
        case "Pickrate*":
            return "% of time picked, when available"
        case "W on 4":
            return "Workers on Wave 4"
        case "W on 10":
            return "Workers on Wave 10"
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
        case _:
            return header.capitalize()
  
def get_key_value(data, key, k, games, stats="", elo = 0, specific_tier = False, dict_type = None):
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
        case "Pickrate" | "Playrate" | "Usage Rate" | "Pickrate*":
            try:
                if stats != "spellstats" or (specific_tier == True and stats == "spellstats"):
                    return f"{custom_winrate([data[key]['Count'], games])}%"
                else:
                    return f"{custom_winrate([data[key]['Count'], data[key]['Offered']])}%"
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
                if stats != "spellstats" or (specific_tier == True and stats == "spellstats"):
                    pickrate = custom_winrate([data[key]['Count'], games])
                else:
                    pickrate = custom_winrate([data[key]['Count'], data[key]['Offered']])
            except Exception:
                pickrate = 0
            if specific_tier and pickrate < 10:
                pickrate = pickrate * 1.5
            if dict_type:
                stats = dict_type
                tier_dict = {"mmstats": [68,62,59,55,0.4], "openstats": [53,40,30,20,0.2],
                             "spellstats": [55,45,35,25,0.4], "unitstats": [55,50,45,40,0.1],
                             "rollstats": [55,50,45,40,0.1], "megamindstats": [52,51,50,49,0]}
            else:
                tier_dict = {"mmstats": [68,62,59,55,0.4], "openstats": [57,50,40,25,0.2],
                             "spellstats": [67,62,59,55,0.4], "unitstats": [60,57,52,47,0.2],
                             "rollstats": [68,65,59,56,0.3], "megamindstats": [52,51,50,49,0]}
            elo = str(elo)
            elo_dict = {"2800": 0, "2600": 0, "2400": 0, "2200": 0.01, "2000": 0.02, "1800": 0.03}
            if elo not in elo_dict:
                elo = "1800"
            tier_score = (winrate*(elo_dict[elo]*2+1)) + (pickrate * (tier_dict[stats][4]-elo_dict[elo]))
            if (winrate > 80) and (pickrate < 10):
                tier_score = tier_score/2
            if pickrate < 5:
                tier_score = tier_score/2
            if winrate < 50:
                tier_score -= tier_dict[stats][0]/20
            if tier_score >= tier_dict[stats][0]+tier_dict[stats][0]/10:
                return "S+"
            elif tier_score >= tier_dict[stats][0]:
                return "S"
            elif tier_score >= tier_dict[stats][1]:
                return "A"
            elif tier_score >= tier_dict[stats][2]:
                return "B"
            elif tier_score >= tier_dict[stats][3]:
                return "C"
            else:
                return "D"
        case "Best Opener":
            try:
                return get_perf_list(data[key], 'Opener')[0]
            except Exception:
                return 0
        case "Best Spell":
            try:
                return get_perf_list(data[key], 'Spells')[0]
            except KeyError:
                try:
                    return get_perf_list(data[key], 'Spell')[0]
                except Exception:
                    return 0
            except IndexError:
                return None
        case "Best Add":
            try:
                return get_perf_list(data[key], 'OpenWith')[0]
            except IndexError:
                return None
        case "Best Roll":
            try:
                return get_perf_list(data[key], 'Rolls')[0]
            except IndexError:
                return None
        case "Best Combo":
            return get_perf_list(data[key], 'ComboUnit')[0]
        case "Best MMs":
            return get_perf_list(data[key], 'MMs')[0]
        case "Best Merc":
            try:
                return get_perf_list(data[key], 'Mercs')[0]
            except IndexError:
                return None
        case "Best Unit":
            try:
                return get_perf_list(data[key], 'Units')[0]
            except IndexError:
                return None
        case "Endrate":
            return f"{custom_winrate([data[key]['EndCount'], games])}%"
        case "Sendrate":
            return f"{custom_winrate([data[key]['SendCount']/4, data[key]['Count']])}%"
        case "Avg Leak":
            wave_num = findall(r'\d+', key)
            return f"{round(data[key]["LeakedGold"]/(wave_values[int(wave_num[0])-1]*(data[key]["Count"]*4))*100,1)}%"

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
        return str(round(day_diff)) + " days ago"
    if day_diff < 31:
        return str(round(day_diff/7)) + " weeks ago"
    if day_diff < 365:
        return str(round(day_diff/30)) + " months ago"
    return str(round(day_diff/365)) + " years ago"

def get_rank_url(elo):
    if elo >= 2800:
        rank_url = 'https://cdn.legiontd2.com/icons/Ranks/Legend.png'
    elif elo >= 2600:
        rank_url = 'https://cdn.legiontd2.com/icons/Ranks/Grandmaster.png'
    elif elo >= 2400:
        rank_url = 'https://cdn.legiontd2.com/icons/Ranks/SeniorMaster.png'
    elif elo >= 2200:
        rank_url = 'https://cdn.legiontd2.com/icons/Ranks/Master.png'
    elif elo >= 2000:
        rank_url = 'https://cdn.legiontd2.com/icons/Ranks/Expert.png'
    elif elo >= 1800:
        rank_url = 'https://cdn.legiontd2.com/icons/Ranks/Diamond.png'
    elif elo >= 1600:
        rank_url = 'https://cdn.legiontd2.com/icons/Ranks/Platinum.png'
    elif elo >= 1400:
        rank_url = 'https://cdn.legiontd2.com/icons/Ranks/Gold.png'
    elif elo >= 1200:
        rank_url = 'https://cdn.legiontd2.com/icons/Ranks/Silver.png'
    else:
        rank_url = 'https://cdn.legiontd2.com/icons/Ranks/Bronze.png'
    return rank_url

def get_avg_end_wave(data:dict) -> str:
    wave_total = 0
    count = 0
    for wave in data:
        wave_total += int(re.findall(r'\d+', wave)[0]) * data[wave]["EndCount"]
        count += data[wave]["EndCount"]
    return f"{round(wave_total/count, 1)}"
        