import datetime
import time
import itertools

from concurrent.futures import ThreadPoolExecutor, as_completed
from requests_futures.sessions import FuturesSession
import boto3
from flask import Flask


application = Flask(__name__)

application.config.from_object('config')
application.config.from_pyfile('flask.cfg', silent=True)


def group(iterable, n):
    it = iter(iterable)
    while True:
        chunk = tuple(itertools.islice(it, n))
        if not chunk:
            return
        yield chunk


def login_ticket():
    return boto3.resource('s3').Object('seigestats', 'ticket').get()['Body'].read().decode('utf-8')


def profile_ids():
    pages = boto3.client('dynamodb', region_name='us-west-2').get_paginator('scan').paginate(TableName='siegestats-profiles')
    for page in pages:
        for item in page['Items']:
            yield item['profileId']['S']


def online_players(ids, ticket):
    num_online = 0
    total = 0
    session = FuturesSession(max_workers=50)
    futures = map(
        lambda chunk: session.get(
            "https://public-ubiservices.ubi.com:443/v1/profiles/connections?offset=0&limit=50&profileIds=" + ','.join(chunk),
            headers={"Authorization": "Ubi_v1 t=" + ticket, "Ubi-AppId": "39baebad-39e5-4552-8c25-2c9b919064e2"}
        ), group(ids, 50)
    )
    for future in as_completed(futures):
        resp = future.result()
        if not resp.status_code == 200:
            print(resp.status_code, resp.text)
            continue
        total += 50
        for connection in resp.json()['connections']:
            if "5172a557-50b5-4665-b7db-e3f2e8c5041d" not in connection['spaceIds']:
                continue
            num_online += 1
            yield connection
    print("Found {} of about {} players online".format(num_online, total))


def store_connections(connections):
    with boto3.resource('dynamodb', region_name='us-west-2').Table('siegestats-profiles').batch_writer(overwrite_by_pkeys=["profileId"]) as batch:
        for connection in connections:
            batch.put_item(
                Item={
                    "profileId": connection['profileId'],
                    "lastOnline": datetime.datetime.utcnow().isoformat(),
                    "lastModifiedDate": connection['lastModifiedDate']
                }
            )


@application.route("/update_online_players", methods=['POST'])
def update_online_players():
    print("Updating online players...")
    store_connections(online_players(profile_ids(), login_ticket()))
    print("Finished updating online players.")
    return "Message procesed", 200


@application.route("/")
def main():
    return "I'm online!"


if __name__ == "__main__":
    application.run()


