from playfab import PlayFabClientAPI, PlayFabSettings
import threading
import json
import time
from datetime import datetime, timedelta

# Cache for on-demand leaderboard pages
_leaderboard_cache = {}
_cache_duration = timedelta(minutes=15)  # Cache for 15 minutes

# Session management
_session_lock = threading.Lock()
_is_logged_in = False
_last_login_time = None
_session_duration = timedelta(hours=1)  # Re-login after 1 hour to be safe

def _get_cache_key(statistic_name, page):
    return f"{statistic_name}_{page}"

def _is_cache_valid(cache_entry):
    if not cache_entry:
        return False
    cache_time = cache_entry.get("timestamp")
    if not cache_time:
        return False
    return datetime.now() - cache_time < _cache_duration

def _ensure_logged_in(max_retries=3):
    """
    Ensures we have an active PlayFab session. Only logs in if needed.
    Returns True if logged in successfully, False otherwise.
    Thread-safe.
    """
    global _is_logged_in, _last_login_time
    
    with _session_lock:
        # Check if we need to login
        needs_login = (
            not _is_logged_in or 
            _last_login_time is None or 
            datetime.now() - _last_login_time > _session_duration
        )
        
        if not needs_login:
            return True
        
        PlayFabSettings.TitleId = "9092"
        login_request = {
            "TitleId": "9092",
            "CustomId": "LTD2Website",
            "CreateAccount": False
        }
        
        for attempt in range(max_retries):
            login_event = threading.Event()
            login_success = False
            
            def login_callback(success, failure):
                nonlocal login_success
                if success:
                    login_success = True
                login_event.set()
            
            PlayFabClientAPI.LoginWithCustomID(login_request, login_callback)
            login_event.wait(timeout=10)  # 10 second timeout
            
            if login_success:
                _is_logged_in = True
                _last_login_time = datetime.now()
                return True
            
            # Wait before retry
            if attempt < max_retries - 1:
                time.sleep(1 * (attempt + 1))  # Exponential-ish backoff
        
        print(f"Failed to login to PlayFab after {max_retries} attempts")
        _is_logged_in = False
        return False

def leaderboard_task(count=1):
    # Available statistics to fetch first page for
    statistics = [
        "overallEloThisSeasonAtLeastOneGamePlayed",
        "overallPeakEloThisSeasonAtLeastOneGamePlayed"
    ]

    if not _ensure_logged_in():
        print("Failed to login for leaderboard task")
        return

    # Fetch first page (offset 0) for all statistics
    for statistic_name in statistics:
        leaderboard_request = {
            "TitleId": "9092",
            "CustomId": "LTD2Website",
            "CreateAccount": False,
            "StartPosition": 0,
            "StatisticName": statistic_name,
            "MaxResultsCount": 100,
            "ProfileConstraints": {
                "ShowDisplayName": True,
                "ShowStatistics": True,
                "ShowLocations": True,
                "ShowAvatarUrl": True,
                "ShowContactEmailAddresses": True
            }
        }
        
        result_event = threading.Event()
        result_data = None
        
        def make_leaderboard_callback(stat_name):
            def cb(success, failure):
                nonlocal result_data
                if success:
                    if len(success) < 1:
                        print(f"leaderboard fetch error for {stat_name}")
                    elif success.get("Leaderboard", None):
                        result_data = success
                        # Save default statistic to leaderboard_temp.json for backward compatibility
                        if stat_name == "overallEloThisSeasonAtLeastOneGamePlayed":
                            with open(f"leaderboard_temp.json", "w") as f:
                                json.dump(success, f)
                        # Cache the first page
                        cache_key = _get_cache_key(stat_name, 0)
                        _leaderboard_cache[cache_key] = {
                            "data": success,
                            "timestamp": datetime.now()
                        }
                else:
                    if failure:
                        print(f"Something went wrong with the Leaderboard request for {stat_name}")
                result_event.set()
            return cb
        
        PlayFabClientAPI.GetLeaderboard(leaderboard_request, make_leaderboard_callback(statistic_name))
        result_event.wait()
        time.sleep(2)  # Small delay between requests


def get_leaderboard_page(statistic_name, page=0, use_cache=True):
    """
    Fetch a specific page of the leaderboard for a given statistic.
    Pages are 0-indexed, each page contains 100 entries.
    
    Args:
        statistic_name: The statistic name to fetch
        page: Page number (0-indexed, each page is 100 entries)
        use_cache: Whether to use cached data if available
    
    Returns:
        Dictionary with leaderboard data or None if error
    """
    cache_key = _get_cache_key(statistic_name, page)
    
    # Check cache first
    if use_cache:
        cache_entry = _leaderboard_cache.get(cache_key)
        if _is_cache_valid(cache_entry):
            return cache_entry["data"]
    
    # Ensure we're logged in
    if not _ensure_logged_in():
        return None
    
    leaderboard_request = {
        "StartPosition": page * 100,
        "StatisticName": statistic_name,
        "MaxResultsCount": 100,
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
            # Cache the result
            _leaderboard_cache[cache_key] = {
                "data": success,
                "timestamp": datetime.now()
            }
        else:
            result = None
        result_event.set()
    
    PlayFabClientAPI.GetLeaderboard(leaderboard_request, callback)
    result_event.wait(timeout=10)
    return result


def event_leaderboard_task(count=1):
    # Read the current event points version from defaults.json
    with open("defaults.json", "r") as f:
        defaults_data = json.load(f)
    event_points_version = defaults_data.get("EventPointsVersion", 12)

    if not _ensure_logged_in():
        print("Failed to login for event leaderboard task")
        return

    # Fetch leaderboard pages
    for i in range(count):
        offset = 100 * i
        leaderboard_request = {
            "TitleId": "9092",
            "CustomId": "LTD2Website",
            "CreateAccount": False,
            "StartPosition": offset,
            "StatisticName": "eventPoints",
            "MaxResultsCount": 100,
            "ProfileConstraints": {
                "ShowDisplayName": True,
                "ShowStatistics": True,
                "ShowLocations": True,
                "ShowAvatarUrl": True,
                "ShowContactEmailAddresses": True
            },
            "Version": event_points_version
        }

        result_event = threading.Event()
        result_data = None

        def callback(success: dict, failure):
            nonlocal result_data
            if success:
                if len(success) < 1:
                    print("event leaderboard fetch error")
                elif success.get("Leaderboard", None):
                    result_data = success
                    # Only save the first page to temp file
                    if offset == 0:
                        with open(f"event_leaderboard_temp.json", "w") as f:
                            json.dump(success, f)
            else:
                if failure:
                    print(f"Something went wrong with the Event Leaderboard request for offset {offset}")
            result_event.set()

        PlayFabClientAPI.GetLeaderboard(leaderboard_request, callback)
        result_event.wait()
        time.sleep(2)  # Small delay between requests


def get_playfab_stats(playfabid, result_count=1, statistic_name="overallElo"): #ThisSeasonAtLeastOneGamePlayed
    if not _ensure_logged_in():
        return None
    
    stats_request = {
        "PlayFabId": playfabid,
        "StatisticName": statistic_name,
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

    PlayFabClientAPI.GetLeaderboardAroundPlayer(stats_request, callback)
    result_event.wait(timeout=10)
    return result


def get_playfab_event_stats(playfabid, result_count=1):
    if not _ensure_logged_in():
        return None
    
    # Read the current event points version from defaults.json
    with open("defaults.json", "r") as f:
        defaults_data = json.load(f)
    event_points_version = defaults_data.get("EventPointsVersion", 12)
    
    stats_request = {
        "PlayFabId": playfabid,
        "StatisticName": "eventPoints",
        "MaxResultsCount": result_count,
        "ProfileConstraints": {
            "ShowDisplayName": True,
            "ShowStatistics": True,
            "ShowLocations": True,
            "ShowAvatarUrl": True,
            "ShowContactEmailAddresses": True
        },
        "Version": event_points_version
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

    PlayFabClientAPI.GetLeaderboardAroundPlayer(stats_request, callback)
    result_event.wait(timeout=10)
    return result


def get_profile_from_playfab(playername: str):
    if not _ensure_logged_in():
        return None
    
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

    PlayFabClientAPI.GetAccountInfo(playfab_request, callback)
    result_event.wait(timeout=10)
    return result


def get_profile_from_playfab_by_id(playfab_id: str):
    """
    Get profile information using PlayFab ID instead of display name.
    """
    if not _ensure_logged_in():
        return None
    
    playfab_request = {
        "PlayFabId": playfab_id
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

    PlayFabClientAPI.GetAccountInfo(playfab_request, callback)
    result_event.wait(timeout=10)
    return result