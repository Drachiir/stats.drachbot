from playfab import PlayFabClientAPI, PlayFabSettings
import threading
import json

def leaderboard_task(count=1):
    PlayFabSettings.TitleId = "9092"
    offset = 0
    login_request = {
        "TitleId": "9092",
        "CustomId": "LTD2Website",
        "CreateAccount": False
    }

    leaderboard_request = {
        "TitleId": "9092",
        "CustomId": "LTD2Website",
        "CreateAccount": False,
        "StartPosition": offset,
        "StatisticName": "overallEloThisSeasonAtLeastOneGamePlayed",
        "MaxResultsCount": 100,
        "ProfileConstraints": {
            "ShowDisplayName": True,
            "ShowStatistics": True,
            "ShowLocations": True,
            "ShowAvatarUrl": True,
            "ShowContactEmailAddresses": True
        }
    }

    def callback(success: dict, failure):
        if success:
            if len(success) < 1:
                print("leaderboard fetch error")
                return
            if success.get("Leaderboard", None):
                with open(f"leaderboard.json", "w") as f:
                    json.dump(success, f)
        else:
            if failure:
                print(failure.GenerateErrorReport())

    PlayFabClientAPI.LoginWithCustomID(login_request, callback)

    for i in range(count):
        leaderboard_request["StartPosition"] = 100 * i
        offset = 100 * i
        PlayFabClientAPI.GetLeaderboard(leaderboard_request, callback)


def get_playfab_stats(playfabid, result_count=1):
    PlayFabSettings.TitleId = "9092"
    login_request = {
        "TitleId": "9092",
        "CustomId": "LTD2Website",
        "CreateAccount": False
    }
    stats_request = {
        "PlayFabId": playfabid,
        "StatisticName": "overallEloThisSeasonAtLeastOneGamePlayed",
        "MaxResultsCount": result_count,
        "ProfileConstraints": {
            "ShowDisplayName": True,
            "ShowStatistics": True,
            "ShowLocations": True,
            "ShowAvatarUrl": True,
            "ShowContactEmailAddresses": True
        }
    }
    result_event = threading.Event()
    result = None

    def callback(success, failure):
        nonlocal result
        if success:
            result = success
        else:
            result = None
        result_event.set()

    PlayFabClientAPI.LoginWithCustomID(login_request, callback)
    result_event.wait()
    if result is None:
        return None
    result_event.clear()

    PlayFabClientAPI.GetLeaderboardAroundPlayer(stats_request, callback)
    result_event.wait()
    return result


def get_profile_from_playfab(playername: str):
    PlayFabSettings.TitleId = "9092"
    login_request = {
        "TitleId": "9092",
        "CustomId": "LTD2Website",
        "CreateAccount": False
    }
    playfab_request = {
        "TitleDisplayName": playername
    }

    result_event = threading.Event()
    result = None

    def callback(success, failure):
        nonlocal result
        if success:
            result = success
        else:
            result = None
        result_event.set()

    PlayFabClientAPI.LoginWithCustomID(login_request, callback)
    result_event.wait()
    if result is None:
        return None
    result_event.clear()

    PlayFabClientAPI.GetAccountInfo(playfab_request, callback)
    result_event.wait()
    return result