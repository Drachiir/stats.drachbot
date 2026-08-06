import json
import os
import datetime
import time
import traceback
from datetime import datetime, timedelta, timezone
from peewee import *
import platform
from playhouse.postgres_ext import *
from playhouse.pool import PooledPostgresqlDatabase
import requests
import time
from playhouse.migrate import *
from flask import g

if platform.system().lower() == "windows":
    games_folder = "Games/"
else:
    games_folder = "/shared/"

with open("Files/json/Secrets.json", "r") as f:
    secret_file = json.load(f)
    f.close()


db = PooledPostgresqlDatabase(
    "postgres",
    max_connections=None,
    stale_timeout=None,
    #server_side_cursors=True,
    user=secret_file["pg_user"],
    password=secret_file["pg_password"],
    host=secret_file["pg_host"],
    port="5432",
    thread_safe=True
)

def get_db():
    """Get or open a database connection only when needed."""
    if 'db_conn' not in g:
        g.db_conn = db.connection()
    return g.db_conn

def close_db(exception=None):
    """Close the database connection if it was used."""
    db_conn = g.pop('db_conn', None)
    if db_conn:
        db.close()

class BaseModel(Model):
    class Meta:
        database = db


class PlayerProfile(BaseModel):
    id = AutoField()
    player_id = TextField(unique=True)
    player_name = TextField(index=True)
    avatar_url = TextField(null=True)
    country = TextField(null=True)
    city = TextField(null=True)
    guild_tag = TextField(null=True)
    elo = IntegerField(null=True)
    rank = IntegerField(null=True)
    total_games_played = IntegerField()
    ranked_wins_current_season = IntegerField()
    ranked_losses_current_season = IntegerField()
    ladder_points = IntegerField()
    offset = IntegerField()
    last_updated = DateTimeField()


class GameData(BaseModel):
    id = AutoField()
    game_id = TextField(unique=True)  # "_id"
    queue = TextField(index=True)
    version = TextField(index=True)
    date = DateTimeField(index=True)
    ending_wave = IntegerField()  # "endingWave"
    game_length = IntegerField()  # "gameLength"
    game_elo = IntegerField(index=True)  # "gameElo"
    player_count = IntegerField()  # "playerCount"
    spell_choices = ArrayField(field_class=TextField, index=False)  # "spellChoices"
    left_king_hp = ArrayField(field_class=FloatField, index=False)  # "leftKingPercentHp"
    right_king_hp = ArrayField(field_class=FloatField, index=False)  # "rightKingPercentHp"
    player_ids = ArrayField(field_class=TextField, index=True)  # playersData[playerId]


class PlayerData(BaseModel):
    id = AutoField()
    game_id = ForeignKeyField(GameData, field="game_id")
    player_id = TextField()  # "playerID"
    player_name = TextField()  # "playerName"
    player_slot = IntegerField()  # "playerSlot"
    legion = TextField()
    workers = FloatField()
    fighter_value = IntegerField()  # "value"
    game_result = TextField()  # "gameResult"
    player_elo = IntegerField()  # "overallElo"
    elo_change = IntegerField()  # "eloChange"
    fighters = TextField()
    spell = TextField()  # "chosenSpell"
    spell_location = TextField()  # "chosenSpellLocation"
    party_size = IntegerField()
    opener = TextField()  # "firstWaveFighters"
    roll = TextField()  # "rolls"
    party_members = ArrayField(field_class=TextField, index=False)  # "partyMembers"
    party_members_ids = ArrayField(field_class=TextField, index=False)  # "partyMembersIds"
    mvp_score = IntegerField()  # "mvpScore"
    net_worth_per_wave = ArrayField(field_class=IntegerField, index=False)  # "netWorthPerWave"
    fighter_value_per_wave = ArrayField(field_class=IntegerField, index=False)  # "valuePerWave"
    workers_per_wave = ArrayField(field_class=FloatField, index=False)  # "workersPerWave"
    income_per_wave = ArrayField(field_class=IntegerField, index=False)  # "incomePerWave"
    mercs_sent_per_wave = ArrayField(field_class=TextField, index=False)  # "mercenariesSentPerWave"
    mercs_received_per_wave = ArrayField(field_class=TextField, index=False)  # "mercenariesReceivedPerWave"
    leaks_per_wave = ArrayField(field_class=TextField, index=False)  # "leaksPerWave"
    build_per_wave = ArrayField(field_class=TextField, index=False)  # "buildPerWave"
    leak_value = IntegerField()  # "leakValue"
    leaks_caught_value = IntegerField()  # "leaksCaughtValue"
    kingups_sent_per_wave = ArrayField(field_class=TextField, index=False)  # "kingUpgradesPerWave"
    kingups_received_per_wave = ArrayField(field_class=TextField, index=False)  # "opponentKingUpgradesPerWave"
    megamind = BooleanField()
    champ_location = TextField()  # "chosenChampionLocation"
    double_down = BooleanField()
    magic_lamp = BooleanField(null=True)


def _is_deadlock(exc):
    return "deadlock" in str(exc).lower()


def _retry_on_deadlock(fn, max_retries=3, best_effort=False):
    for attempt in range(max_retries):
        try:
            return fn()
        except OperationalError as e:
            if not _is_deadlock(e) or attempt + 1 >= max_retries:
                if best_effort:
                    traceback.print_exc()
                    return None
                raise
            time.sleep(0.05 * (2 ** attempt))
    return None


def _join_waves(waves):
    return ["" if len(wave) == 0 else "!".join(wave) for wave in waves]


def save_game(data):
    date_format = "%Y-%m-%dT%H:%M:%S"
    players = sorted(data["playersData"], key=lambda p: p["playerId"])
    pids = [player["playerId"] for player in players]
    if len(pids) != 4 and len(pids) != 8 and len(pids) != 2:
        if len(pids) != 0:
            print("Odd number of pids for game" + data["_id"])
        else:
            print("Less than 4/8 player ids for game " + data["_id"])
        return
    if GameData.get_or_none(GameData.game_id == data["_id"]) is not None:
        return

    player_rows = []
    for player in players:
        try:
            megamind = player["megamind"]
            champ_location = player["chosenChampionLocation"]
        except Exception:
            megamind = False
            champ_location = "N/A"

        try:
            double_down = player["doubledown"]
        except Exception:
            double_down = False

        try:
            magic_lamp = player["magic_lamp"]
        except Exception:
            magic_lamp = False

        game_result = player["gameResult"] if player["gameResult"] is not None else "Tied"
        player_rows.append(dict(
            game_id=data["_id"],
            player_id=player["playerId"],
            player_name=player["playerName"],
            player_slot=player["playerSlot"],
            legion=player["legion"],
            workers=player["workers"],
            fighter_value=player["value"],
            game_result=game_result,
            player_elo=player["overallElo"],
            elo_change=player["eloChange"],
            fighters=player["fighters"],
            spell=player["chosenSpell"],
            spell_location=player["chosenSpellLocation"],
            party_size=player["partySize"],
            opener=player["firstWaveFighters"],
            roll=player["rolls"],
            party_members=player["partyMembers"],
            party_members_ids=player["partyMembersIds"],
            mvp_score=player["mvpScore"],
            net_worth_per_wave=player["netWorthPerWave"],
            fighter_value_per_wave=player["valuePerWave"],
            workers_per_wave=player["workersPerWave"],
            income_per_wave=player["incomePerWave"],
            mercs_sent_per_wave=_join_waves(player["mercenariesSentPerWave"]),
            mercs_received_per_wave=_join_waves(player["mercenariesReceivedPerWave"]),
            leaks_per_wave=_join_waves(player["leaksPerWave"]),
            build_per_wave=_join_waves(player["buildPerWave"]),
            leak_value=player["leakValue"],
            leaks_caught_value=player["leaksCaughtValue"],
            kingups_sent_per_wave=_join_waves(player["kingUpgradesPerWave"]),
            kingups_received_per_wave=_join_waves(player["opponentKingUpgradesPerWave"]),
            megamind=megamind,
            champ_location=champ_location,
            double_down=double_down,
            magic_lamp=magic_lamp
        ))

    def insert_game():
        with db.atomic():
            if GameData.get_or_none(GameData.game_id == data["_id"]) is not None:
                return
            GameData(
                game_id=data["_id"],
                queue=data["queueType"],
                version=data["version"],
                date=datetime.strptime(data["date"].split(".")[0], date_format),
                ending_wave=data["endingWave"],
                game_length=data["gameLength"],
                game_elo=data["gameElo"],
                player_count=data["playerCount"],
                spell_choices=data["spellChoices"],
                left_king_hp=data["leftKingPercentHp"],
                right_king_hp=data["rightKingPercentHp"],
                player_ids=pids
            ).save()
            for row in player_rows:
                PlayerData(**row).save()

    _retry_on_deadlock(insert_game)


if __name__ == '__main__':  # "incomenchill": false, "votedmode": null "availablemode": 6,
    migrator = PostgresqlMigrator(db)
    # migrate(
    #     migrator.add_column(
    #         'playerdata',
    #         'magic_lamp',
    #         BooleanField(default=False, null=False)
    #     )
    # )
    quit()