import util

player_map = {1:[1,2,3],2:[0,3,2],5:[3,1,0],6:[2,0,1]}

def matchupstats(playerid, games, patch, min_elo = 0, max_elo = 9001, history_raw = {}):
    if type(history_raw) == str:
        return history_raw
    games = len(history_raw)
    if games == 0:
        return 'No games found.'
    gameelo_list = []
    mmnames_list = util.mm_list[:]
    mmnames_list.remove("Megamind")
    masterminds_dict = {}
    for x in mmnames_list:
        masterminds_dict[x] = {"Count": 0, "Wins": 0, "Elo": 0, "Teammates": {}, "Enemies1": {}, "Enemies2": {}}
    for game in history_raw:
        gameelo_list.append(game["game_elo"])
        for player in game["players_data"]:
            if playerid != "all" and playerid != player["player_id"]:
                continue
            if player["legion"] not in masterminds_dict:
                continue

            teammate = game["players_data"][player_map[player["player_slot"]][0]]
            enemy1 = game["players_data"][player_map[player["player_slot"]][1]]
            enemy2 = game["players_data"][player_map[player["player_slot"]][2]]

            masterminds_dict[player["legion"]]["Count"] += 1
            masterminds_dict[player["legion"]]["Elo"] += player["player_elo"]

            if not teammate["legion"] in masterminds_dict[player["legion"]]["Teammates"]:
                masterminds_dict[player["legion"]]["Teammates"][teammate["legion"]] = {"Wins": 0, "Count": 0}
            if not enemy1["legion"] in masterminds_dict[player["legion"]]["Enemies1"]:
                masterminds_dict[player["legion"]]["Enemies1"][enemy1["legion"]] = {"Wins": 0, "Count": 0}
            if not enemy2["legion"] in masterminds_dict[player["legion"]]["Enemies2"]:
                masterminds_dict[player["legion"]]["Enemies2"][enemy2["legion"]] = {"Wins": 0, "Count": 0}

            masterminds_dict[player["legion"]]["Teammates"][teammate["legion"]]["Count"] += 1
            masterminds_dict[player["legion"]]["Enemies1"][enemy1["legion"]]["Count"] += 1
            masterminds_dict[player["legion"]]["Enemies2"][enemy2["legion"]]["Count"] += 1

            if player["game_result"] == "won":
                masterminds_dict[player["legion"]]["Wins"] += 1
                masterminds_dict[player["legion"]]["Teammates"][teammate["legion"]]["Wins"] += 1
                masterminds_dict[player["legion"]]["Enemies1"][enemy1["legion"]]["Wins"] += 1
                masterminds_dict[player["legion"]]["Enemies2"][enemy2["legion"]]["Wins"] += 1

    try:
        avg_gameelo = round(sum(gameelo_list) / len(gameelo_list))
    except ZeroDivisionError:
        avg_gameelo = 0

    # After iterating through all games, merge Enemies1 and Enemies2 into Enemies
    for mmname in masterminds_dict:
        merged_enemies = {}
        enemies1 = masterminds_dict[mmname]["Enemies1"]
        enemies2 = masterminds_dict[mmname]["Enemies2"]

        # Add enemies from Enemies1
        for legion, data in enemies1.items():
            merged_enemies[legion] = {"Wins": data["Wins"], "Count": data["Count"]}

        # Merge in enemies from Enemies2
        for legion, data in enemies2.items():
            if legion not in merged_enemies:
                merged_enemies[legion] = {"Wins": data["Wins"], "Count": data["Count"]}
            else:
                merged_enemies[legion]["Wins"] += data["Wins"]
                merged_enemies[legion]["Count"] += data["Count"]

        masterminds_dict[mmname]["Enemies"] = merged_enemies
    
    newIndex = sorted(masterminds_dict, key=lambda x: masterminds_dict[x]['Count'], reverse=True)
    masterminds_dict = {k: masterminds_dict[k] for k in newIndex}
    
    return [masterminds_dict, games, avg_gameelo]
