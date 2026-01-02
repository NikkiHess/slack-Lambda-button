#!/usr/bin/env python3

"""
The Slack Lambda Button module for the Duderstadt Center

Author:
Nikki Hess (nkhess@umich.edu)
"""

# built-in
import time
import threading
from typing import List

# pypi
import boto3

# my modules
import sheets
import aws
from nikki_utils import tsprint
import config

lambda_client, sqs_client = aws.setup_aws()

SLACK_CONFIG = config.get_and_verify_config_data("config/slack.json")
BOT_OAUTH_TOKEN = SLACK_CONFIG["bot_oauth_token"]

BUTTON_CONFIG = config.get_and_verify_config_data("config/button.json")
tsprint(f"Button ID is {BUTTON_CONFIG.get('device_id', '')}")

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

    tsprint("Getting device config.")

    last_row = sheets.find_first_empty_row(sheets_service, spreadsheet_id)
    all_rows = sheets.get_region(sheets_service, spreadsheet_id, tab_name="Config",
                                        first_row = 2, last_row = last_row,
                                        first_letter = "A", last_letter = "I")

    for idx, row in enumerate(all_rows, start=2):  # Google Sheets is 1-indexed
        if len(row) > 1 and row[1].strip() == device_id:
            tsprint(f"Got device info: {row}")
            return row
    
    tsprint(f"ERROR: Unable to get device config. Device {device_id} was not listed. Exiting.")
    exit(1)
    return device_info

def handle_interaction(aws_client: boto3.client, sheets_service, spreadsheet_id, do_post: bool = True) -> dict | None:
    """
    Handles a button press or screen tap, basically just does the main functionality

    Args:
        aws_client (boto3.client): the AWS client we're using
        do_post (bool): whether to post to the Slack or just log in console, for debug
        press_length (float): how long was the button pressed?

    Returns:
        the posted message id, if there is one OR None
    """
    
    tsprint("Interaction received, handling.")

    # set up Google Sheets and grab the config
    device_id = BUTTON_CONFIG["device_id"]
    device_config = get_config(sheets_service, spreadsheet_id, device_id)

    device_message = device_config[4]
    device_rate_limit = int(device_config[7])
    device_channel_id = device_config[8]

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
    pass
