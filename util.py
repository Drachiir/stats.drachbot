from datetime import datetime


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
        if dict2[key][xy]['Wins'] / dict2[key][xy]['Count'] < dict2['Wins'] / dict2['Count']:
            continue
        new_dict[xy] = dict2[key][xy]['Wins'] / dict2[key][xy]['Count'] * (dict2[key][xy]['Count'] / dict2['Count'])
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
        case "Opener" | "Openers" | "Best Opener" | "Adds" | "Best Add" | "Unit" | "Best Combo" | "Combos" | "Targets" | "unitstats" | "openstats":
            return f"https://cdn.legiontd2.com/icons/{get_unit_name(string)}.png"
        case "MM" | "MMs" | "Best MMs" | "mmstats":
            return f"https://cdn.legiontd2.com/icons/Items/{string}.png"
        case "Spell" | "Spells" | "Best Spells" | "Best Spell" | "spellstats":
            return f"https://cdn.legiontd2.com/icons/{get_unit_name(string).replace('PresstheAttack', 'PressTheAttack').replace('None', 'Granddaddy')}.png"

def get_tooltip(header:str):
    header = str(header)
    if header.startswith("Best"):
        if header == "Best Add":
            return f"Best Unit built within the first 4 waves based on Win% and Play%"
        return f"Best {header.split(" ")[1]} based on Win% and Play%"
    match header:
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
        case _:
            return header.capitalize()
  
def get_key_value(data, key, k, games, stats=""):
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
                if stats != "spellstats":
                    return f"{custom_winrate([data[key]['Count'], games])}%"
                else:
                    return f"{custom_winrate([data[key]['Offered'], games])}%"
            except Exception:
                return 0
        case "Player Elo":
            return int(custom_divide([data[key]['Elo'], data[key]['Count']]))
        case "W on 10":
            return custom_divide([data[key]['Worker'], data[key]['Count']], 1)
        case "W on 4":
            return custom_divide([data[key]['Worker'], data[key]['Count']], 1)
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
        case "Best Combo":
            return get_perf_list(data[key], 'ComboUnit')[0]
        case "Best MMs":
            return get_perf_list(data[key], 'MMs')[0]

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