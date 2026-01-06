# built-in
import unittest
from unittest.mock import Mock
import io
import json

# my modules
import aws

class TestPostToSlack(unittest.TestCase):
	def test_post_to_slack(self):
		# define stuff both the mock response and function call need
		message = "test message"
		channel_id = "C12345"
		device_id = "Mock1"

		# prepare mock AWS client whose invoke() returns a Payload-like object
		mock_client = Mock()
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
		self.assertEqual((posted_id, posted_channel), (response_payload["posted_message_id"], response_payload["posted_message_channel"]))

        # verify invoke was called exactly once
		mock_client.invoke.assert_called_once()

        # verify that the arguments were the expected ones
		kwargs = mock_client.invoke.call_args[1]
		self.assertEqual(kwargs["FunctionName"], "slackLambda-dev")
		sent_payload = json.loads(kwargs["Payload"])
		self.assertIn("body", sent_payload)
		self.assertEqual(sent_payload["body"]["message"], message)
		self.assertEqual(sent_payload["body"]["channel_id"], channel_id)
		self.assertEqual(sent_payload["body"]["device_id"], device_id)


if __name__ == "__main__":
	unittest.main()
