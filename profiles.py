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


async def _profiles():
    base = "https://public-ubiservices.ubi.com/v2/profiles?profileIds="
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
            ], 50
        )
    ]
    print("Built " + str(len(futures)) + " futures")
    profiles = []
    for future in futures:
        try:
            response = await future
            response.raise_for_status()
            for profile in response.json()["profiles"]:
                profiles.append(profile)
        except Exception as e:
            print(e)
            print(sys.exc_info()[0])
            pass
    print("Found " + str(len(profiles)) + " profiles")
    import pymysql.cursors

    connection = pymysql.connect(
        host='r6tracker.c26zdjdyszm5.us-east-1.rds.amazonaws.com',
        user='r6tracker',
        password=boto3.client('ssm', region_name='us-east-1').get_parameter(Name='r6tracker-db-pw', WithDecryption=True)['Parameter']['Value'],
        db='r6tracker',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

    try:
        with connection.cursor() as cursor:
            head = "INSERT INTO `profiles` (`profileId`, `profile`, `profileHash`) VALUES "
            tail = " ON DUPLICATE KEY UPDATE profile=profile"
            for p in chunks(profiles, 100):
                cursor.execute(
                    head +
                    ','.join(
                        [
                            "('" +
                            profile["profileId"] + "','" +
                            json.dumps(profile) + "','" +
                            hashlib.sha1(json.dumps(profile).encode("utf-8")).hexdigest() +
                            "')"
                            for profile in p
                        ]
                    ) +
                    tail
                )
                connection.commit()
    finally:
        connection.close()
    print("Done")


def profiles():
    loop = asyncio.new_event_loop()
    loop.run_until_complete(_profiles())
