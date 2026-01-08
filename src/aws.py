#!/usr/bin/env python3

"""
Code for interacting with AWS.

Author:
Nikki Hess (nkhess@umich.edu)
"""

# built-in
import json

# pypi
import boto3

# my modules
from nikki_utils import tsprint
from . import config

LATEST_MESSAGE = None # latest SQS message
STOP_THREAD = False

def post_to_slack(aws_client: boto3.client, message: str, channel_id: str,
                  device_id: str, dev: bool):
    """
    Posts a message to Slack using chat.postMessage

    :param aws_client: the AWS client we're using
    :type aws_client: boto3.client

    :param message: the message to send
    :type message: str

    :param channel_id: the Slack channel to send the message to
    :type channel_id: str

    :param device_id: the device id associated with the message
    :type device_id: str

    :param dev: whether we're using the dev AWS instance
    :type dev: bool
    """

    tsprint("Posting message to Slack via AWS.")

    payload = {
        "body": {
            "type": "post",
            "message": message,
            "channel_id": channel_id,
            "device_id": device_id
        }
    }
    payload = json.dumps(payload) # convert dict to string

    tsprint(f"AWS Payload: {payload}")

    # the function name is apparently the name of the instance ¯\_(ツ)_/¯
    response = aws_client.invoke(
        FunctionName="slackLambda" + "-dev" if dev else "",
        Payload=payload
    )
    
    tsprint(f"AWS Response: {response}")

    # extract our custom response
    response = response["Payload"].read().decode("utf-8")
    response = json.loads(response)

    # this should be guaranteed with a post payload
    return response.get("posted_message_id"), response.get("posted_message_channel")

def mark_message_timed_out(aws_client: boto3.client, message_id: str, channel_id: str, dev: bool):
    """
    Edits a message on Slack to mark it timed out

    :param aws_client: the AWS client we're using
    :type aws_client: boto3.client

    :param message_id: the message id to edit
    :type message_id: str

    :param channel_id: the Slack channel to send the message to
    :type channel_id: str

    :param dev: whether we're using the dev AWS instance
    :type dev: bool
    """
    tsprint(f"Marking message {message_id} as timed out.")

    payload = {
        "body": {
            "type": "message_timeout",
            "message_id": message_id,
            "channel_id": channel_id
        }
    }
    payload = json.dumps(payload) # convert dict to string

    tsprint(f"AWS Payload: {payload}")

    # invoke the AWS Lambda function
    response = aws_client.invoke(
        FunctionName="slackLambda" + "-dev" if dev else "",
        Payload=payload
    )
    
    tsprint(f"AWS Response: {response}")

def mark_message_replied(aws_client: boto3.client, message_id: str, channel_id: str, dev: bool):
    """
    Edits a message on Slack to mark it replied

    :param aws_client: the AWS client we're using
    :type aws_client: boto3.client

    :param message_id: the message id to edit
    :type message_id: str

    :param channel_id: the Slack channel to send the message to
    :type channel_id: str

    :param dev: whether we're using the dev AWS instance
    :type dev: bool
    """

    tsprint(f"Marking message {message_id} as replied.")

    payload = {
        "body": {
            "type": "message_replied",
            "message_id": message_id,
            "channel_id": channel_id
        }
    }
    payload = json.dumps(payload) # convert dict to string

    tsprint(f"AWS Payload: {payload}")

    # invoke the AWS Lambda function
    response = aws_client.invoke(
        FunctionName="slackLambda" + "-dev" if dev else "",
        Payload=payload
    )
    
    tsprint(f"AWS Response: {response}")

def poll_sqs(sqs_client: boto3.client, device_id: str):
    """
    Periodically polls SQS, will run on a separate thread

    :param sqs_client: the SQS client we're using
    :type sqs_client: boto3.client

    :param device_id: the id of the device we're on
    :type device_id: str
    """
    global LATEST_MESSAGE, STOP_THREAD

    tsprint(f"Starting SQS poll loop for device {device_id}")
    queue_url = "https://sqs.us-east-2.amazonaws.com/225753854445/slackLambda-dev.fifo"

    while True:
        if STOP_THREAD:
            tsprint("Stopping SQS poll loop.")
            STOP_THREAD = False
            break

        response = sqs_client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=3 # no hammering AWS >:()
        )

        # has to be obtained as a list first
        messages = response.get("Messages", [])

        if messages:
            message = messages[0] # get the first item

            # process the message
            message_body = message["Body"]
            message_body = json.loads(message_body) # load into JSON
            message_body = message_body["Message"] # get message
            message_body = json.loads(message_body) # load into JSON again

            tsprint(f"SQS message received: {message_body}")
            if "reply_text" in message_body.keys():
                LATEST_MESSAGE = message_body

            # delete from queue after process
            sqs_client.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=message["ReceiptHandle"]
            )
            tsprint("Deleted SQS message from queue.")

def setup_aws() -> boto3.client:
    """
    Sets up the AWS client

    :return: a tuple of (lambda_client, sqs_client)
    :rtype: (boto3.client, boto3.client)
    """

    tsprint("Setting up AWS.")

    global AWS_CONFIG, SLACK_CONFIG, SQS_CLIENT

    AWS_CONFIG = config.get_and_verify_config_data(config_path="config/aws.json")
    SLACK_CONFIG = config.get_and_verify_config_data(config_path="config/slack.json")

    access_key = AWS_CONFIG["aws_access_key"]
    secret = AWS_CONFIG["aws_secret"]
    region = AWS_CONFIG["region"]

    # set up lambda client
    client = boto3.client(
        "lambda",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret,
        region_name=region
    )

    # set up sqs client
    SQS_CLIENT = boto3.client(
        "sqs",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret,
        region_name=region
    )

    tsprint("AWS successfully set-up.")
    tsprint("Returning AWS clients.")

    return client, SQS_CLIENT