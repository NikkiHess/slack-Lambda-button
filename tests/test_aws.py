# built-in
import pytest
from pytest_mock import MockerFixture
from pytest_mock import mocker
import io
import json

# my modules
from src import aws

def test_post_to_slack(mocker: MockerFixture):
	# setup
	message_id = "123"
	channel_id = "C999"
	mock_client = mocker.Mock()
	mock_client.invoke.return_value = {
		"Payload": io.BytesIO(json.dumps({
			"posted_message_id": message_id,
			"posted_message_channel": channel_id
		}).encode("utf-8"))
	}

	# call the function with the mock client, to avoid actual API call
	posted_id, posted_channel = aws.post_to_slack(
		mock_client,
		"test",
		message_id,
		"Mock1",
		dev=True
	)

	# assert that we're returning the expected values
	assert posted_id == "123"
	assert posted_channel == "C999"

	# assert that the client invokes "AWS" exactly once
	mock_client.invoke.assert_called_once()

def test_mark_message_timed_out(mocker: MockerFixture):
	# setup
	message_id = "123"
	channel_id = "C999"
	mock_client = mocker.Mock()
	mock_client.invoke.return_value = {
		"Payload": io.BytesIO(json.dumps({
			"type": "message_timeout",
			"posted_message_id": message_id,
			"posted_message_channel": channel_id
		}).encode("utf-8"))
	}

	# call the function with the mock client, to avoid actual API call
	resp = aws.mark_message_timed_out(
		mock_client,
		message_id,
		channel_id,
		True
	)

	# assert that we're returning the expected values
	assert resp["type"] == "message_timeout"
	assert resp["posted_message_id"] == message_id
	assert resp["posted_message_channel"] == channel_id

	# assert that the client invokes "AWS" exactly once
	mock_client.invoke.assert_called_once()

def test_mark_message_replied(mocker: MockerFixture):
	# setup
	message_id = "123"
	channel_id = "C999"
	mock_client = mocker.Mock()
	mock_client.invoke.return_value = {
		"Payload": io.BytesIO(json.dumps({
			"type": "message_timeout",
			"posted_message_id": message_id,
			"posted_message_channel": channel_id
		}).encode("utf-8"))
	}

	# call the function with the mock client, to avoid actual API call
	resp = aws.mark_message_replied(
		mock_client,
		message_id,
		channel_id,
		True
	)

	# assert that we're returning the expected values
	assert resp["type"] == "message_timeout"
	assert resp["posted_message_id"] == message_id
	assert resp["posted_message_channel"] == channel_id

	# assert that the client invokes "AWS" exactly once
	mock_client.invoke.assert_called_once()

def test_poll_sqs(mocker: MockerFixture, capsys: pytest.CaptureFixture[str]):
	mock_client = mocker.Mock()
	message_dict = {
		"ts": "1767897585.233119",
		"reply_text": "test",
		"reply_author": "Nikki"
	}

	# SQS outputs JSON strings, not actual JSON
	sqs_message = {
		"Body": json.dumps({"Message": json.dumps(message_dict)}),
		"ReceiptHandle": "RECEIPT123"
	}

	# set STOP_THREAD so poll_sqs exits after one loop
	# also sets the return value
	def receive_side_effect(*args, **kwargs):
		aws.STOP_THREAD = True
		return {"Messages": [sqs_message]}
	
	mock_client.receive_message.side_effect = receive_side_effect

	aws.poll_sqs(mock_client, "Mock1")
	captured = capsys.readouterr()

	assert f"] SQS message received: {message_dict}" in captured.out
	mock_client.delete_message.assert_called_once()
	called_kwargs = mock_client.delete_message.call_args[1]
	assert called_kwargs["ReceiptHandle"] == "RECEIPT123"