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

def get_unit_name(name):
    if not name:
        return ""
    new_string = ""
    for string in name.split(" "):
        new_string += string.capitalize()
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
    if new_string == "PackRat(footprints)":
        new_string = "PackRat(Footprints)"
    if new_string == "PackRatNest":
        new_string = "PackRat(Footprints)"
    if new_string == "Aps":
        new_string = "APS"
    if new_string == "Mps":
        new_string = "MPS"
    return new_string