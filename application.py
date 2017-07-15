import datetime
import time
import itertools

import requests
import boto3
from flask import Flask


application = Flask(__name__)


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
    table = boto3.resource('dynamodb', region_name='us-west-2').Table('siegestats-profiles')
    resp = table.scan()
    for item in resp['Items']:
        yield item['profileId']
    while 'LastEvalutatedKey' in resp:
        resp = table.scan(ExclusiveStartKey=resp['LastEvaluatedKey'])
        for item in resp['Items']:
            yield item['profileId']


def online_players(ids, ticket):
    num_online = 0
    for chunk in group(ids, 50):
        resp = requests.get(
            "https://public-ubiservices.ubi.com:443/v1/profiles/connections?offset=0&limit=50&profileIds=" + ','.join(chunk),
            headers={
                "Authorization": "Ubi_v1 t=" + ticket,
                "Ubi-AppId": "39baebad-39e5-4552-8c25-2c9b919064e2"
            }
        )

        resp.raise_for_status()

        online = [
            connection for connection in resp.json()['connections']
            if "5172a557-50b5-4665-b7db-e3f2e8c5041d" not in connection['spaceIds']
        ]
        num_online += len(online)
        for connection in online:
            yield connection
    print("Found {} players online".format(num_online))


def store_connections(connections):
    with boto3.resource('dynamodb', region_name='us-west-2').Table('siegestats-profiles').batch_writer() as batch:
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
    application.run(port=80)


