#!/usr/bin/env python3

"""
The Slack Lambda Button module for the Duderstadt Center

Author:
Nikki Hess (nkhess@umich.edu)
"""

# built-in
import time
import threading
import re

# pypi
import boto3

# my modules
from . import sheets
from . import aws
from nikki_utils import tsprint
from . import config

lambda_client, sqs_client = aws.setup_aws()

SLACK_CONFIG = config.get_and_verify_config_data("config/slack.json")
BOT_OAUTH_TOKEN = SLACK_CONFIG["bot_oauth_token"]

BUTTON_CONFIG = config.get_and_verify_config_data("config/button.json")
tsprint(f"Button ID is {BUTTON_CONFIG.get('device_id', '')}")

# Dictionary to store the timestamp of the last message sent for each button
LAST_MESSAGE_TIMESTAMP = {}

def get_device_config(sheets_service, spreadsheet_id: int, device_id: str) -> dict[str, str]:
    """
    Gets the configuration for a button from Google Sheets
    and returns it as a List

    :param sheets_service: the Google Sheets service we're working with
    :type sheets_service: object

    :param spreadsheet_id: the id of the spreadsheet we're working on
    :type spreadsheet_id: int

    :param device_id: the id of this specific device, received from slack.json
    :type device_id: str

    :return: the dictionary of column name -> config value
    :rtype: dict
    """
    tsprint("Getting device config.")

    last_row = sheets.find_first_empty_row(sheets_service, spreadsheet_id)
    all_rows = sheets.get_region(sheets_service, spreadsheet_id, tab_name="Config",
                                        first_row = 1, last_row = last_row,
                                        first_letter = "A", last_letter = "J")

    # put titles in device config dict in order
    keys = []
    for title in all_rows[0]:
        title = title.lower().replace("#", "num")
        title = re.sub(r"\s+", "_", title)
        title = re.sub(r"\(|\)", "", title)

        keys.append(title)

    for row in all_rows[1:]:
        if len(row) > 1 and row[1].strip() == device_id:
            tsprint(f"Got device info: {row}")
            # combine keys and row (device config)
            device_config_dict = dict(zip(keys, row))

            return device_config_dict
    
    tsprint(f"ERROR: Unable to get device config. Device {device_id} was not listed. Exiting.")
    exit(1)

def handle_interaction(aws_client: boto3.client, sheets_service, spreadsheet_id, do_post: bool = True) -> dict | None:
    """
    Handles a button press or screen tap, basically just does the main functionality

    :param aws_client: the AWS client we're using
    :type aws_client: boto3.client

    :param sheets_service: the Google Sheets service to use
    :type sheets_service: object

    :param spreadsheet_id: the spreadsheet id to use
    :type spreadsheet_id: int

    :param do_post: whether to post to the Slack or just log in console, for debug
    :type do_post: bool

    :return: the posted message id and channel id (tuple) if posted, otherwise None
    :rtype: (str, str) | None
    """
    
    tsprint("Interaction received, handling.")

    # set up Google Sheets and grab the config
    device_id = BUTTON_CONFIG["device_id"]
    device_config = get_device_config(sheets_service, spreadsheet_id, device_id)

    device_message = device_config["message"]
    device_rate_limit = int(device_config["rate_limit_seconds"])
    device_channel_id = device_config["channel_id"]

    # handle timestamp, check for rate limit
    last_timestamp = LAST_MESSAGE_TIMESTAMP.get(device_id, 0)
    current_timestamp = time.time()

    if current_timestamp - last_timestamp < device_rate_limit:
        tsprint("Rate limit applied. Message not sent.")
        return {"statusCode": 429, "body": "Rate limit applied."}

    # handle empty message/location
    if device_message is None or device_message == "":
        final_message = "Unknown button pressed."
    else:
        final_message = device_message

    tsprint(f"Message retrieved from config: {final_message}")

    # handle long button presses by sending a test message
    final_message += "\n*To respond, reply to this message in a thread within 3 minutes*\n*To resolve, react with :white_check_mark: or :+1:*"

    # if we post to Slack, we need to go through AWS and return a message/channel id
    if do_post:
        result_container = {}

        def aws_worker():
            message_id, channel_id = aws.post_to_slack(
                aws_client, final_message, device_channel_id, device_id, True
            )
            LAST_MESSAGE_TIMESTAMP[device_id] = current_timestamp
            tsprint("Message posted to slack.")
            
            # store results for the caller
            result_container["message_id"] = message_id
            result_container["channel_id"] = channel_id

        tsprint(f"Starting AWS worker thread to post message for device {device_id}")
        thread = threading.Thread(target=aws_worker, daemon=True)
        thread.start()
        thread.join()  # wait for the thread to finish so we can return values
        tsprint(f"AWS message posting finished for device {device_id}: message_id={result_container.get('message_id')} channel_id={result_container.get('channel_id')}")

        return result_container.get("message_id"), result_container.get("channel_id")
    
    # else not needed here cuz return
    return None

if __name__ == "__main__":
    # config_file: the config file that we created or opened
    # sheets_service: the Google Sheets service we used
    # spreadsheet: the spreadsheet gotten/created
    # spreadsheet_id: the spreadsheet's id, for convenience
    # tabs: the tabs listed in the config
    
    _, sheets_service, _, spreadsheet_id, _ = sheets.setup_sheets()
    get_device_config(
        sheets_service=sheets_service,
        spreadsheet_id=spreadsheet_id,
        device_id="Dev1"
    )