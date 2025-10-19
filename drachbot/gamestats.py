import util
from drachbot.peewee_pg import GameData, PlayerData

def gamestats(playerid = "all", history_raw = {}):
    gameelo_list = []
    option_key = "mercs_sent_per_wave"
    option_key2 = "kingups_sent_per_wave"
    if type(history_raw) == str:
        return history_raw
    if len(history_raw) == 0:
        return 'No games found.'
    wave_dict = {}
    wave1_dict = {"Snail":0, "Save":0, "King": {"Upgrade King Attack": 0, "Upgrade King Spell": 0, "Upgrade King Regen": 0}}
    dd_dict = {"Wins": 0, "Count": 0, "EloChange": 0}
    games = len(history_raw)
    game_length = 0
    for i in range(1, 22):
        wave_dict[f"wave{i}"] = {"Count": 0, "EndCount": 0, "SendCount": 0, "LeakedGold": 0,
                                 "PowerMerc": 0, "IncomeMerc": 0, "Value": 0, "Worker": 0, "Income": 0}
    for game in history_raw:
        gameelo_list.append(game["game_elo"])
        wave_dict[f"wave{game["ending_wave"]}"]["EndCount"] += 1
        game_length += game["game_length"]
        for player in game["players_data"]:
            if player["player_id"] != playerid and playerid != "all":
                continue

            try:
                if player["double_down"]:
                    dd_dict["Count"] += 1
                    dd_dict["EloChange"] += player["elo_change"]
                    if player["game_result"] == "won":
                        dd_dict["Wins"] += 1
            except Exception:
                pass

            for i in range(game["ending_wave"]):
                wave_dict[f"wave{i + 1}"]["Count"] += 1
                try:
                    wave_dict[f"wave{i + 1}"]["Worker"] += player["workers_per_wave"][i]
                    wave_dict[f"wave{i + 1}"]["Income"] += player["income_per_wave"][i]
                    wave_dict[f"wave{i + 1}"]["Value"] += player["fighter_value_per_wave"][i]
                    send_total = 0
                    if player["workers_per_wave"][i] > 5:
                        small_send = (player["workers_per_wave"][i] - 5) / 4 * 20
                    else:
                        small_send = 0
                    if player[option_key][i]:
                        send = util.count_mythium(player[option_key][i], seperate=True)
                        send_total = sum(send)
                        wave_dict[f"wave{i + 1}"]["IncomeMerc"] += send[0]
                        wave_dict[f"wave{i + 1}"]["PowerMerc"] += send[1]
                    if player[option_key2][i]:
                        send_total += len(player[option_key2][i].split("!")) * 20
                        wave_dict[f"wave{i + 1}"]["IncomeMerc"] += len(player[option_key2][i].split("!")) * 20
                    if send_total > small_send:
                        wave_dict[f"wave{i + 1}"]["SendCount"] += 1
                    if player["leaks_per_wave"][i]:
                        wave_dict[f"wave{i + 1}"]["LeakedGold"] += util.calc_leak(player["leaks_per_wave"][i], i, return_gold=True)
                except IndexError:
                    continue
            if len(player[option_key][0]) > 0:
                if player[option_key][0].split("!")[0] == 'Snail':
                    wave1_dict["Snail"] += 1
            elif len(player[option_key2][0]) > 0:
                wave1_dict["King"][str(player[option_key2][0].split("!")[0])] += 1
            else:
                wave1_dict["Save"] += 1
    avg_gameelo = round(sum(gameelo_list) / len(gameelo_list))

    try:
        dd_winrate = round(dd_dict["Wins"] / dd_dict["Count"] * 100, 1)
    except ZeroDivisionError:
        dd_winrate = 0
    dd_dict["Winrate"] = dd_winrate

    return [wave_dict, wave1_dict, game_length, games, avg_gameelo, dd_dict]