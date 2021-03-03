import json
import sys

import requests
from requests.adapters import HTTPAdapter
from slack import WebClient
from slack.errors import SlackApiError
from urllib3 import Retry
import arrow

with open("config.json") as cfg:
    config = json.load(cfg)

paused = "paused" in config and bool(config["paused"]) is True
if paused:
    print('Updating paused.')
    sys.exit(0)

timezone = 'UTC'
if 'timezone' in config:
    timezone = config['timezone']

extended_siesta = "extended_siesta" in config and bool(config["extended_siesta"]) is True

client = WebClient(token=config["token"])

session = requests.Session()
retry = Retry(
    total=3,
    read=3,
    connect=3,
    backoff_factor=0.3,
    status_forcelist=(500, 502, 504),
)
adapter = HTTPAdapter(max_retries=retry)
session.mount('http://', adapter)
session.mount('https://', adapter)

front_matter = []
if extended_siesta:
    front_matter.append("*Grand Siesta*")

sim_data = session.get(config["base_url"] + '/database/simulationData').json()

if "eraTitle" in sim_data and len(sim_data["eraTitle"]) > 0:
    era_desc = "*" + sim_data["eraTitle"]
    if "subEraTitle" in sim_data and len(sim_data["subEraTitle"]) > 0:
        era_desc += f": _{sim_data['subEraTitle']}_"
    front_matter.append(era_desc + "*")

time_desc = ""
if "season" in sim_data:
    time_desc += f"Season {sim_data['season'] + 1}"
    if "phase" in sim_data:
        if sim_data["phase"] == 0:
            time_desc += " - Gods' Day"
        if sim_data["phase"] == 1:
            time_desc += " - Preseason"
        if sim_data["phase"] == 2:
            time_desc += " - Earlseason"
        if sim_data["phase"] == 3:
            time_desc += " - Earlsiesta"
        if sim_data["phase"] == 4:
            time_desc += " - Midseason"
        if sim_data["phase"] == 5:
            time_desc += " - Latesiesta"
        if sim_data["phase"] == 6:
            time_desc += " - Lateseason"
        if sim_data["phase"] == 7:
            time_desc += " - Endseason"
        if sim_data["phase"] == 8:
            time_desc += " - Earlpostseason"
        if sim_data["phase"] == 9:
            time_desc += " - Latepostseason"
        if sim_data["phase"] == 10:
            time_desc += " - Election"
    if sim_data["phase"] in [8, 9] and "playOffRound" in sim_data:
        time_desc += f" - Postseason Round {sim_data['playOffRound'] + 1}"
    if "day" in sim_data:
        time_desc += f" - Day {sim_data['day'] + 1}"
        if sim_data['day'] == 68:
            time_desc += " ⁿᶦᶜᵉ"

front_matter.append(time_desc)

all_msgs = []
for obj in session.get(config["base_url"] + '/database/globalEvents').json():
    all_msgs.append(obj['msg'])


def diff(first, second):
    second = set(second)
    return [item for item in first if item not in second]


added = diff(all_msgs, config["last_seen"]["all_msgs"] or [])
print("Added: ", added)
removed = diff(config["last_seen"]["all_msgs"] or [], all_msgs)
print("Removed: ", removed)

updated_time = arrow.now(timezone)
update_time_human = updated_time.format('MMM D, YYYY [at] h:mm A (ZZZ)')

current_message = ""
for item in front_matter:
    current_message += f"⚾ {item}\n"
if len(front_matter) > 0:
    current_message += "\n"

current_message += f"Ticker messages as of {update_time_human}:```\n" + "\n".join(all_msgs) + "\n```"

chan_id = None
current_topic = None
channel_member = None
for conv in client.conversations_list(limit=1000)["channels"]:
    if conv["name"] == config["channel"] and conv["is_channel"] is True:
        chan_id = conv["id"]
        current_topic = conv["topic"]["value"]
        channel_member = conv["is_member"]
        break

if chan_id is None:
    print("Failed to find channel #" + config["channel"])
    sys.exit(1)

if not channel_member:
    print(f"Not currently in channel channel #{config['channel']}, joining now.")
    client.conversations_join(channel=chan_id)

start_new_day = not extended_siesta

print_diffs = False
if "message_ts" in config:
    print_diffs = True
    message_timestamp = arrow.get(float(config["message_ts"]))
    start_new_day = start_new_day and message_timestamp.to(timezone).date() != updated_time.date()
    if not start_new_day:
        client.chat_update(channel=chan_id, ts=config["message_ts"], text=current_message, parse="none")
    else:
        try:
            client.pins_remove(channel=chan_id, timestamp=config["message_ts"])
        except SlackApiError as e:
            print("Failed to unpin: ", e)
        del config["message_ts"]

if start_new_day:
    chat_msg = client.chat_postMessage(channel=chan_id, text=current_message, parse="none")
    config["message_ts"] = chat_msg.get("ts")
    client.chat_postMessage(channel=chan_id, text="This post will be edited with the latest ticker messages throughout the (human) day. This thread will contain a log of the changes. Follow it if you want to keep up with the latest incinerations, peanut swallowings, etc.", thread_ts=config["message_ts"])
    if 'owner_id' in config:
        client.chat_postMessage(channel=chan_id, text=f"If this bot goes completely heywire, please ping <@{config['owner_id']}>!", thread_ts=config["message_ts"])
    client.pins_add(channel=chan_id, timestamp=config["message_ts"])


def plural(msgs):
    if len(msgs) == 1:
        return "Message"
    else:
        return "Messages"


if print_diffs and (len(added) > 0 or len(removed) > 0):
    update_msg = f"*Updates at {update_time_human}*\n"
    if len(removed) > 0:
        update_msg += f"{plural(removed)} removed:\n"
        for msg in removed:
            update_msg += f"```\n{msg}\n```\n"
    if len(added) > 0:
        update_msg += f"{plural(added)} added:\n"
        for msg in added:
            update_msg += f"```\n{msg}\n```\n"

    client.chat_postMessage(channel=chan_id, text=update_msg, thread_ts=config["message_ts"])

config["last_seen"] = {
    "all_msgs": all_msgs,
}

with open("config.json", "wt") as cfg:
    json.dump(config, cfg, indent=2)
