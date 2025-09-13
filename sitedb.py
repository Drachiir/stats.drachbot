import sqlite3
from datetime import datetime, timezone
import requests


def init_db():
    conn = sqlite3.connect("site.db")
    cursor = conn.cursor()
    
    # Create table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            discord_id TEXT PRIMARY KEY,
            username TEXT,
            discriminator TEXT,
            avatar TEXT,
            player_id TEXT,
            created_at TIMESTAMP,
            last_login TIMESTAMP,
            hide_country_flag INTEGER DEFAULT 0,
            ltd2_playername TEXT,
            ltd2_avatar_url TEXT,
            private_profile INTEGER DEFAULT 0
        );
    """)
    
    # Check if new columns exist and add them if they don't
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'ltd2_playername' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN ltd2_playername TEXT")
        print("Added ltd2_playername column to users table")
    
    if 'ltd2_avatar_url' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN ltd2_avatar_url TEXT")
        print("Added ltd2_avatar_url column to users table")
    
    if 'private_profile' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN private_profile INTEGER DEFAULT 0")
        print("Added private_profile column to users table")
    
    conn.commit()
    conn.close()

def save_user_to_db(user_data, player_id, ltd2_playername=None, ltd2_avatar_url=None):
    conn = sqlite3.connect("site.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (discord_id, username, discriminator, avatar, player_id, last_login, ltd2_playername, ltd2_avatar_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(discord_id) DO UPDATE SET
            username = excluded.username,
            discriminator = excluded.discriminator,
            avatar = excluded.avatar,
            player_id = excluded.player_id,
            last_login = excluded.last_login,
            ltd2_playername = excluded.ltd2_playername,
            ltd2_avatar_url = excluded.ltd2_avatar_url;
    """, (
        user_data["id"],
        user_data["username"],
        user_data["discriminator"],
        user_data["avatar"],
        player_id,
        datetime.now(tz=timezone.utc),
        ltd2_playername,
        ltd2_avatar_url
    ))
    conn.commit()
    conn.close()

def get_player_id(discord_id):
    try:
        response = requests.get("https://verify.drachbot.site/player-id", params={"discord_id": discord_id}, timeout=5)

        print(response)
        # Handle 404 - user not found (no linked account)
        if response.status_code == 404:
            print(f"No linked LTD2 account found for discord_id {discord_id}")
            return None
            
        response.raise_for_status()
        data = response.json()
        return data.get("player_id")
    except requests.RequestException as e:
        print("Error fetching player_id:", e)
        return None

def get_user_preferences(discord_id):
    conn = sqlite3.connect("site.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT hide_country_flag, private_profile FROM users WHERE discord_id = ?
    """, (discord_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return {"hide_country_flag": bool(result[0]), "private_profile": bool(result[1])}
    return {"hide_country_flag": False, "private_profile": False}

def update_user_preferences(discord_id, preferences):
    conn = sqlite3.connect("site.db")
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users SET hide_country_flag = ?, private_profile = ? WHERE discord_id = ?
    """, (int(preferences.get("hide_country_flag", False)), 
          int(preferences.get("private_profile", False)), 
          discord_id))
    conn.commit()
    conn.close()

def get_user_ltd2_data(discord_id):
    conn = sqlite3.connect("site.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ltd2_playername, ltd2_avatar_url FROM users WHERE discord_id = ?
    """, (discord_id,))
    result = cursor.fetchone()
    conn.close()
    return {"ltd2_playername": result[0], "ltd2_avatar_url": result[1]} if result else {"ltd2_playername": None, "ltd2_avatar_url": None}

def is_profile_private(player_id):
    conn = sqlite3.connect("site.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT private_profile FROM users WHERE player_id = ?
    """, (player_id,))
    result = cursor.fetchone()
    conn.close()
    return bool(result[0]) if result else False