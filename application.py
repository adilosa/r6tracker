from players_online import players_online
from players import players
from profiles import profiles

from flask import Flask


application = Flask(__name__)

application.config.from_object('config')
application.config.from_pyfile('flask.cfg', silent=True)


@application.route("/players_online", methods=['POST'])
def update_online_players():
    print("Updating online players...")
    players_online()
    print("Finished updating online players.")
    return "Message procesed", 200


@application.route("/players", methods=['POST'])
def update_players():
    print("Updating players...")
    players()
    print("Finished updating players.")
    return "Message procesed", 200


@application.route("/profiles", methods=['POST'])
def update_profiles():
    print("Updating profiles...")
    profiles()
    print("Finished updating profiles.")
    return "Message procesed", 200


@application.route("/")
def main():
    return "I'm online!"


if __name__ == "__main__":
    application.run()
