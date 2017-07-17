import datetime
import time
import itertools

import grequests
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
    pages = boto3.client('dynamodb', region_name='us-west-2').get_paginator('scan').paginate(TableName='siegestats-profiles')
    for page in pages:
        for item in page['Items']:
            yield item['profileId']['S']


def online_players(ids, ticket):
    num_online = 0
    total = 0

    resps = grequests.imap(
        map(
            lambda chunk: grequests.get(
                "https://public-ubiservices.ubi.com:443/v1/profiles/connections?offset=0&limit=50&profileIds=" + ','.join(chunk),
                headers={ "Authorization": "Ubi_v1 t=" + ticket, "Ubi-AppId": "39baebad-39e5-4552-8c25-2c9b919064e2" }
            ), group(ids, 50)
        ), size=50, exception_handler=lambda r, e: print(e)
    )
    for resp in resps:
        if not resp.status_code == 200:
            print(resp.status_code, resp.text)
            continue
        for connection in resp.json()['connections']:
            total += 1
            if "5172a557-50b5-4665-b7db-e3f2e8c5041d" not in connection['spaceIds']:
                continue
            num_online += 1
            yield connection
    print("Found {} of about {} players online".format(num_online, total))


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


