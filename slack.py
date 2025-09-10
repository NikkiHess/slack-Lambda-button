#!/usr/bin/env python3

"""
The Slack Lambda Button module for the Duderstadt Center

Author:
Nikki Hess (nkhess@umich.edu)
"""

import json
import sys
import time

from typing import List

from datetime import datetime
from subprocess import DEVNULL, STDOUT, check_call
import requests
from requests.exceptions import RequestException
import boto3

import sheets
import aws

lambda_client, sqs_client = aws.setup_aws()
is_raspberry_pi = not sys.platform.startswith("win32")

config_defaults = {"bot_oauth_token": "", "button_config": {"device_id": ""}}

# Read the configuration files
try:
    with open("config/slack.json", "r", encoding="utf8") as file:
        slack_config = json.load(file)

        # if we don't have all required keys, populate the defaults
        if not all(slack_config.get(key) for key in config_defaults.keys()):
            with open("config/slack.json", "w", encoding="utf8") as write_file:
                json.dump(config_defaults, write_file)
except (FileNotFoundError, json.JSONDecodeError):
    with open("config/slack.json", "w+", encoding="utf8") as file:
        print("config/slack.json not found or wrong, creating + populating defaults...")

        json.dump(config_defaults, file)
        print("Please fill out config/slack.json before running again.")
    exit()

BUTTON_CONFIG = slack_config["button_config"]
BOT_OAUTH_TOKEN = slack_config["bot_oauth_token"]

# Dictionary to store the timestamp of the last message sent for each button
LAST_MESSAGE_TIMESTAMP = {}

def get_config(sheets_service, spreadsheet_id: int, device_id: str) -> List[str]:
    """
    Gets the configuration for a button from Google Sheets
    and returns it as a List

    Args:
        sheets_service: the Google Sheets service we're working with
        spreadsheet_id (int): the id of the spreadsheet we're working on
        device_id (str): the id of this specific device, received from slack.json
    """

    last_row = sheets.find_first_empty_row(sheets_service, spreadsheet_id)

    device_id_list = sheets.get_region(sheets_service, spreadsheet_id,
                                        first_row = 2, last_row = last_row,
                                        first_letter = "B", last_letter = "B")

    device_id_list = [id[0].strip() if id != [] else "" for id in device_id_list]
    try:
        # add 2 because skip first row + Google Sheets is 1 indexed
        device_index = device_id_list.index(device_id) + 2
    except ValueError:
        print(f"Unable to get device config. Device {device_id} was not listed. Exiting.")
        sys.exit()

    try:
        device_info = sheets.get_region(sheets_service, spreadsheet_id,
                                        first_row = device_index, last_row = device_index,
                                        first_letter = "A", last_letter = "I")[0]
    except IndexError:
        print("Index out of range when selecting device config. Did you forget to set the device ID (slack.json)?")
        sys.exit()

    return device_info

def get_datetime() -> str | None:
    """
    Gets the current datetime as a beautifully formatted string

    Returns:
        formatted_time (str | None): the formatted time string, if present
    """

    formatted_time = None
    try:
        response = requests.get(
            "https://timeapi.io/api/time/current/zone?timeZone=America%2FDetroit",
            timeout=3
        )
        response.raise_for_status() # prevent uncatchable errors
        response_data = response.json()
        iso_datetime = response_data["dateTime"]

        if "." in iso_datetime:
            date_part, frac = iso_datetime.split(".")
            frac = frac[:6]  # keep only first 6 digits
            iso_datetime = f"{date_part}.{frac}"

        current_time = datetime.fromisoformat(iso_datetime)
        formatted_time = current_time.strftime("%B %d, %Y %I:%M:%S %p")
    except (requests.exceptions.Timeout, json.decoder.JSONDecodeError, RequestException):
        # Fall back on system time, though potentially iffy
        now = datetime.now()
        formatted_time = now.strftime("%B %d, %Y %I:%M:%S %p")

    return formatted_time

def handle_interaction(aws_client: boto3.client, do_post: bool = True) -> str | None:
    """
    Handles a button press or screen tap, basically just does the main functionality

    Args:
        aws_client (boto3.client): the AWS client we're using
        do_post (bool): whether to post to the Slack or just log in console, for debug
        press_length (float): how long was the button pressed?

    Returns:
        the posted message id, if there is one OR None
    """

    press_type = "SINGLE"

    # set up Google Sheets and grab the config
    _, sheets_service, _, _, spreadsheet_id = sheets.setup_sheets("google_config")
    device_id = BUTTON_CONFIG["device_id"]

    device_config = get_config(sheets_service, spreadsheet_id, device_id)

    device_location = device_config[3]
    device_message = device_config[4]
    device_rate_limit = int(device_config[7])
    device_channel_id = device_config[8]

    # handle timestamp, check for rate limit
    last_timestamp = LAST_MESSAGE_TIMESTAMP.get(device_id, 0)
    current_timestamp = time.time()

    if current_timestamp - last_timestamp < device_rate_limit:
        print("Rate limit applied. Message not sent.")
        return {"statusCode": 429, "body": "Rate limit applied."}

    # handle empty message/location
    if device_message is None or device_message == "":
        final_message = "Unknown button pressed."
    else:
        final_message = device_message

    print(f"Message retrieved from config: {final_message}")

    # handle long button presses by sending a test message
    final_message += "\n*To respond, reply to this message in a thread within 3 minutes*\n*To resolve, react with :white_check_mark: or :+1:*"

    # if we post to Slack, we need to go through AWS and return a message/channel id
    if do_post:
        message_id, channel_id = aws.post_to_slack(aws_client, final_message, device_channel_id, device_id, True)

        LAST_MESSAGE_TIMESTAMP[device_id] = current_timestamp

        return message_id, channel_id
    # else not needed here cuz return

    return None, None

if __name__ == "__main__":
    print(get_datetime(True))
