import drachbot.legion_api as legion_api
import util

def wavestats(playerid, games, min_elo, patch, sort="date", history_raw = {}):
    gameelo_list = []
    if type(history_raw) == str:
        return history_raw
    if len(history_raw) == 0:
        return 'No games found.'
    wave_dict = {}
    games = len(history_raw)
    for i in range(1,22):
        wave_dict[f"wave{i}"] = {"Count": 0, "EndCount": 0, "SendCount": 0, "LeakedGold": 0, "Mercs": {}, "Units": {}}
    for game in history_raw:
        gameelo_list.append(game["game_elo"])
        wave_dict[f"wave{game["ending_wave"]}"]["EndCount"] += 1
        for i in range(game["ending_wave"]):
            wave_dict[f"wave{i+1}"]["Count"] += 1
            for player in game["players_data"]:
                if player["player_id"] != playerid and playerid != "all":
                    continue
                #FIGURE OUT IF THERE WAS A SEND ON THIS WAVE
                if player["mercs_sent_per_wave"][i]:
                    wave_dict[f"wave{i+1}"]["SendCount"] += 1
                    #ITERATE THROUGH MERCS SENT IF THERE WAS A SEND
                    merc_wave_temp = player["mercs_sent_per_wave"][i].split("!")
                    merc_wave = set()
                    for merc in merc_wave_temp:
                        merc = merc.split("_unit_")[0].replace("_", " ")
                        merc_wave.add(merc)
                    for merc in merc_wave:
                        if merc not in wave_dict[f"wave{i+1}"]["Mercs"]:
                            wave_dict[f"wave{i+1}"]["Mercs"][merc] = {"Count": 1, "Wins": 0}
                        else:
                            wave_dict[f"wave{i+1}"]["Mercs"][merc]["Count"] += 1
                        if player["game_result"] == "won":
                            wave_dict[f"wave{i+1}"]["Mercs"][merc]["Wins"] += 1
                elif player["kingups_sent_per_wave"][i]:
                    wave_dict[f"wave{i+1}"]["SendCount"] += 1
                    kingups_list = player["kingups_sent_per_wave"][i].split("!")
                    for kingup in kingups_list:
                        if kingup not in wave_dict[f"wave{i+1}"]["Mercs"]:
                            wave_dict[f"wave{i+1}"]["Mercs"][kingup] = {"Count": 1, "Wins": 0}
                        else:
                            wave_dict[f"wave{i+1}"]["Mercs"][kingup]["Count"] += 1
                        if player["game_result"] == "won":
                            wave_dict[f"wave{i+1}"]["Mercs"][kingup]["Wins"] += 1
                else:
                    if "Save" not in wave_dict[f"wave{i + 1}"]["Mercs"]:
                        wave_dict[f"wave{i + 1}"]["Mercs"]["Save"] = {"Count": 1, "Wins": 0}
                    else:
                        wave_dict[f"wave{i + 1}"]["Mercs"]["Save"]["Count"] += 1
                    if player["game_result"] == "won":
                        wave_dict[f"wave{i + 1}"]["Mercs"]["Save"]["Wins"] += 1
                #ITERATE THROUGH UNITS BUILT
                unit_wave_temp = player["build_per_wave"][i].split("!")
                unit_wave = set()
                for unit in unit_wave_temp:
                    unit = unit.split("_unit_")[0].replace("_", " ")
                    unit_wave.add(unit)
                for unit in unit_wave:
                    if unit not in wave_dict[f"wave{i+1}"]["Units"]:
                        wave_dict[f"wave{i+1}"]["Units"][unit] = {"Count": 1, "Wins": 0}
                    else:
                        wave_dict[f"wave{i+1}"]["Units"][unit]["Count"] += 1
                    if player["game_result"] == "won":
                        wave_dict[f"wave{i+1}"]["Units"][unit]["Wins"] += 1
                #ITERATE THROUGH LEAKED UNITS IF THERE ARE ANY
                if player["leaks_per_wave"][i]:
                    wave_dict[f"wave{i+1}"]["LeakedGold"] += util.calc_leak(player["leaks_per_wave"][i], i, return_gold=True)
    avg_gameelo = round(sum(gameelo_list) / len(gameelo_list))
    return [wave_dict, games, avg_gameelo]