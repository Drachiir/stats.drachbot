import util

def sendstats(playerid, history_raw = {}):
    gameelo_list = []
    if type(history_raw) == str:
        return history_raw
    if len(history_raw) == 0:
        return 'No games found.'
    send_dict = {}
    games = len(history_raw)
    for incmerc in util.incmercs:
        send_dict[incmerc.lower()] = {"Count": 0, "Wins": 0, "WaveCount": 0, "MercsCombo": {}, "Units": {}, "Waves": {}}

    for powermerc in util.powermercs:
        send_dict[powermerc.lower()] = {"Count": 0, "Wins": 0, "WaveCount": 0, "MercsCombo": {}, "Units": {}, "Waves": {}}

    send_to_map = {0: 2, 1: 3, 2: 1, 3: 0}

    total_waves = 0

    for game in history_raw:
        gameelo_list.append(game["game_elo"])
        players_data = game["players_data"]

        for player_index, player in enumerate(players_data):
            if playerid != "all" and player["player_id"] != playerid:
                continue

            total_waves += game["ending_wave"]

            for wave_index in range(game["ending_wave"]):
                mercs_wave_raw = player["mercs_sent_per_wave"][wave_index]
                if not mercs_wave_raw:
                    continue  # No mercs sent this wave

                # Unique mercs sent this wave (normalize)
                merc_names = set()
                for merc_str in mercs_wave_raw.split("!"):
                    merc = merc_str.split("_unit_")[0].replace("_", " ").lower()
                    merc_names.add(merc)

                # Enemy player board
                enemy_index = send_to_map.get(player_index)
                enemy_units = set()
                if enemy_index is not None and enemy_index < len(players_data):
                    enemy_player = players_data[enemy_index]
                    units_raw = enemy_player["build_per_wave"][wave_index]
                    if units_raw:
                        for unit_str in units_raw.split("!"):
                            unit = unit_str.split("_unit_")[0].replace("_", " ").lower()
                            enemy_units.add(unit)

                player_won = player["game_result"] == "won"

                for merc in merc_names:
                    if merc not in send_dict:
                        continue

                    # Count & Win
                    send_dict[merc]["Count"] += 1
                    if player_won:
                        send_dict[merc]["Wins"] += 1

                    # Combos: key by other mercs sent with it
                    for other_merc in merc_names:
                        if other_merc == merc:
                            continue
                        if other_merc not in send_dict[merc]["MercsCombo"]:
                            send_dict[merc]["MercsCombo"][other_merc] = {"Count": 0, "Wins": 0}
                        send_dict[merc]["MercsCombo"][other_merc]["Count"] += 1
                        if player_won:
                            send_dict[merc]["MercsCombo"][other_merc]["Wins"] += 1

                    # Units: enemy board units on that wave
                    for unit in enemy_units:
                        if unit not in send_dict[merc]["Units"]:
                            send_dict[merc]["Units"][unit] = {"Count": 0, "Wins": 0}
                        send_dict[merc]["Units"][unit]["Count"] += 1
                        if player_won:
                            send_dict[merc]["Units"][unit]["Wins"] += 1

                    # Waves: Count & Win for this wave
                    wave_key = f"Wave{wave_index + 1}"
                    if wave_key not in send_dict[merc]["Waves"]:
                        send_dict[merc]["Waves"][wave_key] = {"Count": 0, "Wins": 0}
                    send_dict[merc]["Waves"][wave_key]["Count"] += 1
                    if player_won:
                        send_dict[merc]["Waves"][wave_key]["Wins"] += 1

    avg_gameelo = round(sum(gameelo_list) / len(gameelo_list))

    newIndex = sorted(send_dict, key=lambda x: send_dict[x]['Count'], reverse=True)
    send_dict = {k: send_dict[k] for k in newIndex}

    for send in send_dict:
        send_dict[send]["WaveCount"] = total_waves

    return [send_dict, games, avg_gameelo]