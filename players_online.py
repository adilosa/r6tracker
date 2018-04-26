import sys
import boto3
import json
import asyncio
import functools
from botocore.vendored import requests


def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i + n]


def s3file(bucket, key):
    print(bucket, key)
    return boto3.resource('s3').Object(bucket, key).get()['Body'].read().decode('utf-8')


async def _players_online():
    base = "https://public-ubiservices.ubi.com:443/v1/profiles/connections?offset=0&limit=50&profileIds="
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
            # "86fb0498-0b1b-4d21-b621-310cab9bec15,bcf0ef91-9084-47d9-860d-91a2fdbac260,ec3061f9-968f-4443-b760-0c3dc354c9c2,42bff726-304e-44dd-809f-7d0f312a9300,69d1cb01-ad43-4ff7-b31c-6332ba88b9a8,71c42f4d-96b6-4fb2-a980-39b92529d116,f70cc0da-5a3a-4678-81a0-46b2ad5b17ac".split(","), 50
            [line.rstrip() for line in s3file('seigestats', sys.argv[1]).split("\n")], 50
            # [line.rstrip() for line in open(sys.argv[1])], 50
        )
    ]
    print("Built " + str(len(futures)) + " futures")
    online = []
    for future in futures:
        try:
            response = await future
            online += [
                conn for conn in response.json()["connections"]
                if "5172a557-50b5-4665-b7db-e3f2e8c5041d" in conn["spaceIds"]
            ]
        except Exception as e:
            print(e)
            pass
    print("Found " + str(len(online)) + " players online")
    boto3.resource('s3').Object('seigestats', sys.argv[2]).put(Body=json.dumps(online))
    print("Done")


def players_online():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
