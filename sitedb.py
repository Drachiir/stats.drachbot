import sqlite3
from datetime import datetime, timezone
import requests


def init_db():
    conn = sqlite3.connect("site.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            discord_id TEXT PRIMARY KEY,
            username TEXT,
            discriminator TEXT,
            avatar TEXT,
            player_id TEXT,
            created_at TIMESTAMP,
            last_login TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()

def save_user_to_db(user_data, player_id):
    conn = sqlite3.connect("site.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (discord_id, username, discriminator, avatar, player_id, last_login)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(discord_id) DO UPDATE SET
            username = excluded.username,
            discriminator = excluded.discriminator,
            avatar = excluded.avatar,
            player_id = excluded.player_id,
            last_login = excluded.last_login;
    """, (
        user_data["id"],
        user_data["username"],
        user_data["discriminator"],
        user_data["avatar"],
        player_id,
        datetime.now(tz=timezone.utc)
    ))
    conn.commit()
    conn.close()

def get_player_id(discord_id):
    try:
        response = requests.get("https://verify.drachbot.site/player-id", params={"discord_id": discord_id}, timeout=5)
        response.raise_for_status()
        data = response.json()
        return data.get("player_id")
    except requests.RequestException as e:
        print("Error fetching player_id:", e)
        return None