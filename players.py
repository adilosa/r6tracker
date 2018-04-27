import sys
import boto3
import json
import hashlib
import asyncio
import functools
from botocore.vendored import requests


base = "https://public-ubiservices.ubi.com"


def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i + n]


def s3file(bucket, key):
    return boto3.resource('s3').Object(bucket, key).get()['Body'].read().decode('utf-8')


async def _players():
    base = "https://public-ubiservices.ubi.com/v1/spaces/5172a557-50b5-4665-b7db-e3f2e8c5041d/sandboxes/OSBOR_PC_LNCH_A/r6karma/players?board_id=pvp_ranked&region_id=ncsa&season_id=-1&profile_ids="
    headers = {
        "Authorization":
            "Ubi_v1 t=" + s3file('seigestats', 'ticket'),
        "Ubi-AppId": "39baebad-39e5-4552-8c25-2c9b919064e2"
    }
    loop = asyncio.get_event_loop()
    print("Building futures")
    futures = [
        loop.run_in_executor(
            None, functools.partial(
                requests.get,
                base + ",".join(profiles),
                headers=headers
            )
        )
        for profiles in chunks(
            [
                profile['profileId']
                for profile in json.loads(s3file('seigestats', 'players_online.json'))
            ], 200
        )
    ]
    print("Built " + str(len(futures)) + " futures")
    players = []
    for future in futures:
        try:
            response = await future
            response.raise_for_status()
            for profileId, player in response.json()["players"].items():
                players.append({"profileId": profileId, "player": player})
        except Exception as e:
            print(e)
            print(sys.exc_info()[0])
            pass
    print("Found " + str(len(players)) + " players information")
    import pymysql.cursors

    connection = pymysql.connect(
        host='r6tracker.c26zdjdyszm5.us-east-1.rds.amazonaws.com',
        user='r6tracker',
        password=boto3.client('ssm').get_parameter(Name='r6tracker-db-pw', WithDecryption=True)['Parameter']['Value'],
        db='r6tracker',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

    try:
        with connection.cursor() as cursor:
            head = "INSERT INTO `players` (`profileId`, `player`, `playerHash`) VALUES "
            tail = " ON DUPLICATE KEY UPDATE player=player"
            for p in chunks(players, 100):
                cursor.execute(
                    head +
                    ','.join(
                        [
                            "('" +
                            player["profileId"] + "','" +
                            json.dumps(player["player"]) + "','" +
                            hashlib.sha1(json.dumps(player["player"]).encode("utf-8")).hexdigest() +
                            "')"
                            for player in p
                        ]
                    ) +
                    tail
                )
                connection.commit()
    finally:
        connection.close()
    print("Done")


def players():
    loop = asyncio.new_event_loop()
    loop.run_until_complete(_players())
