# built-in
import pytest
from pytest_mock import mocker
import io
import json

# my modules
from src import aws

def test_post_to_slack(mocker):
	# variables both the mock response and function call need
	message = "test message"
	channel_id = "C12345"
	device_id = "Mock1"

	# prepare mock AWS client whose invoke() returns a Payload-like object
	mock_client = mocker.Mock()
	response_payload = {
		"statusCode": 200,
		"headers": {
			"Content-Type": "text/plain"
		},
		"body": message,
		"posted_message_id": "1234567890.123456",
		"posted_message_channel": channel_id
	}
	mock_client.invoke.return_value = {
		"Payload": io.BytesIO(json.dumps(response_payload).encode("utf-8"))
	}

	# call the function with the mock client, to avoid actual API call
	posted_id, posted_channel = aws.post_to_slack(mock_client, message, channel_id, device_id, True)

	# verify return values
	assert (posted_id, posted_channel) == (response_payload["posted_message_id"], response_payload["posted_message_channel"])

	# verify that the arguments were the expected ones
	kwargs = mock_client.invoke.call_args[1]
	assert kwargs["FunctionName"] == "slackLambda-dev"

	sent_payload = json.loads(kwargs["Payload"])
	assert "body" in sent_payload
	assert sent_payload["body"]["message"] == message
	assert sent_payload["body"]["channel_id"] == channel_id
	assert sent_payload["body"]["device_id"] == device_id

def test_mark_message_timed_out(mocker):
	# variables both the mock response and function call need
	message_id = "1234567890.123456"
	channel_id = "C12345"

	# prepare mock AWS client whose invoke() returns a Payload-like object
	mock_client = mocker.Mock()
	response_payload = {
		'statusCode': 200, 
		'headers': {
			'Content-Type': 'text/plain'
		},
		'body': 'message_timeout',
		'posted_message_id': message_id,
		'posted_message_channel': channel_id
	}
	mock_client.invoke.return_value = {
		"Payload": io.BytesIO(json.dumps(response_payload).encode("utf-8"))
	}

	# call the function with the mock client, to avoid actual API call
	resp = aws.mark_message_timed_out(mock_client, message_id, channel_id, True)

	# verify that we got the parsed response back
	assert resp == response_payload

	# verify that the arguments were the expected ones
	kwargs = mock_client.invoke.call_args[1]
	assert kwargs["FunctionName"] == "slackLambda-dev"

	sent_payload = json.loads(kwargs["Payload"])
	assert "body" in sent_payload
	assert sent_payload["body"]["type"] == "message_timeout"
	assert sent_payload["body"]["message_id"] == message_id
	assert sent_payload["body"]["channel_id"] == channel_id