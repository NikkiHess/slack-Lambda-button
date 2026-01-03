#!/usr/bin/env python3

"""
Makes interfacing with Google Sheets a bit easier.

Author:
Nikki Hess (nkhess@umich.edu)
"""

# built-in
import os
import json
import time
import traceback

# PyPi
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# my modules
from nikki_utils import tsprint
import config

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
CACHE = {}
CACHE_COOLDOWN = 60 * 60 # 60 minutes in seconds

def do_oauth_flow() -> Credentials:
	"""
	Log a user in and return the credentials needed

	:return: OAuth2 user credentials (token)
	:rtype: Credentials
	"""

	tsprint("Starting Google OAuth flow.")
	creds = None

	if os.path.exists("oauth/google_token.json"):
		try:
			creds = Credentials.from_authorized_user_file("oauth/google_token.json", SCOPES)
		except (ValueError, json.JSONDecodeError):
			pass # just don't get creds
	
	# If there are no (valid) credentials available, let the user log in.
	if not creds or not creds.valid:
		if creds and creds.expired and creds.refresh_token:
			try:
				creds.refresh(Request())
				tsprint("Google Cloud token refreshed.")
			except RefreshError: # google RefreshError, need new token
				tsprint("New Google Cloud token needed, running OAuth flow.")

				os.remove("oauth/google_token.json") # clear expired token
				flow = InstalledAppFlow.from_client_secrets_file(
					"oauth/google_credentials.json", SCOPES
				)
				creds = flow.run_local_server(port=0)
		else:
			tsprint("New Google Cloud token needed, running OAuth flow.")

			flow = InstalledAppFlow.from_client_secrets_file(
				"oauth/google_credentials.json", SCOPES
			)
			creds = flow.run_local_server(port=0)
		
		# Save the credentials for the next run
		with open("oauth/google_token.json", "w", encoding="utf8") as token:
			tsprint("Writing new token to file.")
			token.write(creds.to_json())

	tsprint("Google Cloud OAuth flow complete.")
	return creds

def create_spreadsheet(sheets_service, name: str = "Untitled") -> dict:
	"""
	Create a new spreadsheet by name, returns the created spreadsheet

	:param sheets_service: the Google Sheets service to be used
	:type sheets_service: object

	:param name: the name of the spreadsheet to be created
	:type name: str

	:return: the created spreadsheet
	:rtype: dict
	"""

	tsprint(f"Creating a new spreadsheet with name {name}")

	# Properties to create a spreadsheet with
	spreadsheet = {
		"properties": {
			"title": name
		}
	}

	# Call the API to create our new spreadsheet
	spreadsheet = (
		sheets_service
		.spreadsheets()
		.create(body=spreadsheet, fields="spreadsheetId")
		.execute()
	)

	tsprint(f"Spreadsheet with name {name} created successfully!")

	return spreadsheet

def get_spreadsheet(sheets_service, spreadsheet_id: str) -> dict:
	"""
	Gets a spreadsheet by id

	:param sheets_service: the Google Sheets service to be used
	:type sheets_service: object

	:param spreadsheet_id: the spreadsheet id to access
	:type spreadsheet_id: str

	:return: the retrieved spreadsheet, if any
	:rtype: dict
	"""

	tsprint(f"Getting spreadsheet {spreadsheet_id}")

	spreadsheet = None

	cached_spreadsheet = CACHE.get("spreadsheets", {}).get(spreadsheet_id, None)
	cached_contents = cached_spreadsheet.get("contents") if cached_spreadsheet else None
	contents_expiry = cached_spreadsheet.get("contents_expiry") if cached_spreadsheet else None

	if cached_contents is not None and contents_expiry > time.time():
		tsprint(f"Spreadsheet {spreadsheet_id} found in cache. Retrieving.")
		spreadsheet = CACHE["spreadsheets"][spreadsheet_id]["contents"]
	else:
		spreadsheet = sheets_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
		tsprint(f"Got existing spreadsheet with ID: {spreadsheet_id}")
		tsprint("Caching spreadsheet.")

		# we need to make sure the structure exists first by setting a default
		cached_spreadsheet = CACHE.setdefault("spreadsheets", {}).setdefault(spreadsheet_id, {})
		cached_spreadsheet["contents"] = spreadsheet
		cached_spreadsheet["contents_expiry"] = time.time() + CACHE_COOLDOWN

	return spreadsheet

def is_spreadsheet_empty(sheets_service, spreadsheet_id: str, tab_name: str = None) -> bool:
	"""
	Returns whether a given spreadsheet (by ID) is empty.
	For our purposes, this just means that A1 and B1 are empty

	:param sheets_service: the Google Sheets service we're using
	:type sheets_service: object

	:param spreadsheet_id: the spreadsheet to check for emptiness
	:type spreadsheet_id: str

	:param tab_name: the name of the tab to check, if applicable
	:type tab_name: str

	:return: whether the spreadsheet (tab) is empty
	:rtype: bool
	"""

	tab_key = tab_name or "__default__"

	cached_spreadsheet = CACHE.get("spreadsheets", {}).get(spreadsheet_id, None)
	cached_emptiness = (
		cached_spreadsheet
		.get("emptiness", {})
		.get(tab_key)
		if cached_spreadsheet else None
	)
	cached_empty_value = cached_emptiness.get("value", None)
	emptiness_expiry = cached_emptiness.get("expiry", None)

	if cached_empty_value is not None and emptiness_expiry > time.time():
		tsprint(f"Cached value found for spreadsheet (tab {tab_name}) emptiness: {cached_empty_value}")
		return cached_empty_value
	else:
		sheets_range = "A1:B1"
		if tab_name:
			sheets_range = f"{tab_name}!A1:B1"

		try:
			result = (
				sheets_service.spreadsheets()
				.values().get(
					spreadsheetId=spreadsheet_id,
					range=sheets_range
				).execute()
			)

			values = result.get("values", [])
			empty = (len(values) == 0)

			spreadsheet_cache = CACHE.setdefault("spreadsheets", {}).setdefault(spreadsheet_id, {})
			first_empty_cache = spreadsheet_cache.setdefault("emptiness", {})
			first_empty_cache[tab_key] = {
				"value": empty,
				"expiry": time.time() + CACHE_COOLDOWN
			}
			
			tsprint(f"Spreadsheet {spreadsheet_id} {'is' if empty else 'is not'} empty.")

			return empty
		except HttpError as e:
			traceback.format_exc(e)

def find_first_empty_row(sheets_service, spreadsheet_id: str, tab_name: str = None) -> int:
	"""
	Gets the last row of a given spreadsheet

	:param sheets_service: the Google Sheets service to be used
	:type sheets_service: object

	:param spreadsheet_id: the spreadsheet id to access
	:type spreadsheet_id: str

	:param tab_name: the tab name to operate on, if any
	:type tab_name: str

	:return: the first empty row in the spreadsheet
	:rtype: int
	"""
	tsprint(f"Looking for first empty row in spreadsheet {spreadsheet_id} tab {tab_name}")

	tab_key = tab_name or "__default__"

	cached_spreadsheet = CACHE.get("spreadsheets", {}).get(spreadsheet_id, None)
	cached_tab = (
		cached_spreadsheet
		.get("first_empty_row", {})
		.get(tab_key)
		if cached_spreadsheet else None
	)

	cached_index = cached_tab.get("index") if cached_tab else None
	index_expiry = cached_tab.get("expiry") if cached_tab else None

	if cached_index is not None and index_expiry > time.time():
		first_empty = cached_index

		tsprint(f"Cached value found for spreadsheet {spreadsheet_id} first empty row: {first_empty}")
	else:
		sheets_range = "A:A"
		if tab_name:
			sheets_range = f"'{tab_name}'!A:A"

		result = (
			sheets_service.spreadsheets()
			.values()
			.get(
				spreadsheetId=spreadsheet_id,
				range=sheets_range
			)
			.execute()
		)

		values = result.get("values", [])
		first_empty = len(values) + 1

		# write to cache
		spreadsheet_cache = CACHE.setdefault("spreadsheets", {}).setdefault(spreadsheet_id, {})
		first_empty_cache = spreadsheet_cache.setdefault("first_empty_row", {})
		first_empty_cache[tab_key] = {
			"index": first_empty,
			"expiry": time.time() + CACHE_COOLDOWN
		}

		tsprint(f"First empty row for spreadsheet {spreadsheet_id} tab {tab_name} is {first_empty}")

	return first_empty # Return the number of non-empty rows
		
def add_row(sheets_service, spreadsheet_id: str, cells: list[str], tab_name: str = None):
	"""
	Adds a row at the first empty position on the spreadsheet

	:param sheets_service: the Google Sheets service to be used
	:type sheets_service: object

	:param spreadsheet_id: the id of the spreadsheet we're operating on
	:type spreadsheet_id: str

	:param cells: a list of cell contents to set
	:type cells: list[str]

	:param tab_name: the tab name to operate on, if it exists
	:type tab_name: str

	:return: the result of the execution
	:rtype: dict
	"""
	tab_key = tab_name or "__default__"

	next_row = find_first_empty_row(sheets_service, spreadsheet_id, tab_name)

	final_letter = len(cells) - 1
	final_letter += ord('A')
	final_letter = chr(final_letter) # 1 = A, 2 = B, etc.

	# the api-formatted body, containing cell values
	body = {"values": [cells]}

	# the range to select via the API, including the tab (if relevant) and encompassing row/col
	sheets_range = f"A{next_row}:{final_letter}{next_row}"
	if tab_name:
		sheets_range = f"'{tab_name}'!{sheets_range}"

	result = (
		sheets_service.spreadsheets()
		.values()
		.update(
			spreadsheetId=spreadsheet_id,
			range=sheets_range,
			valueInputOption="USER_ENTERED", # follow the same rules as if a user entered this info on the webapp
			body=body
		)
		.execute()
	)

	spreadsheet_cache = CACHE["spreadsheets"].setdefault(spreadsheet_id, {})

	# update first empty row
	spreadsheet_cache = CACHE.setdefault("spreadsheets", {}).setdefault(spreadsheet_id, {})
	first_empty_cache = spreadsheet_cache.setdefault("first_empty_row", {})
	first_empty_cache[tab_key] = {
		"index": next_row + 1,
		"expiry": time.time() + CACHE_COOLDOWN
	}

    # update emptiness, definitely not empty anymore
	first_empty_cache = spreadsheet_cache.setdefault("emptiness", {})
	first_empty_cache[tab_key] = {
		"value": False,
		"expiry": time.time() + CACHE_COOLDOWN
	}

	# invalidate regions cache
	regions_cache = spreadsheet_cache.get("regions", {})
	if tab_key in regions_cache:
		del regions_cache[tab_key]


	tsprint(f"{result.get('updatedCells')} cells added in row {next_row} of spreadsheet {spreadsheet_id} tab {tab_name}: {cells}")
	return result

def get_region(sheets_service, spreadsheet_id: str, tab_name: str = None, 
			   first_row: int = 1, last_row: int = 1,
			   first_letter: str = "A", last_letter: str = "A") -> list[str]:
	"""
	Gets a row in a spreadsheet by index (row_idx)

	:param sheets_service: the Google Sheets service we're using
	:type sheets_service: object

	:param spreadsheet_id: the id of the spreadsheet we're working with
	:type spreadsheet_id: str

	:param tab_name: the name of the tab to select within, defaults to "Sheet1"
	:type tab_name: str

	:param first_row: the first row that we need to get
	:type first_row: int

	:param last_row: the last row that we need to get
	:type last_row: int

	:param first_letter: the first column that we need to get
	:type first_letter: str

	:param last_letter: the last column that we need to get
	:type last_letter: str

	:return: the retrieved region contents (list of rows)
	:rtype: list
	"""

	if first_row < 1 or last_row < 1 or first_letter < "A" or last_letter < "A":
		raise ValueError("Google Sheets starts at A1!")

	# the range to select via the API, including the tab (if relevant) and encompassing row/col
	sheets_range = f"{first_letter}{first_row}:{last_letter}{last_row}"
	if tab_name:
		sheets_range = f"'{tab_name}'!{sheets_range}"

	tsprint(f"Retrieving region {sheets_range} from spreadsheet {spreadsheet_id}")

	tab_key = tab_name or "__default__"

	spreadsheet_cache = CACHE.setdefault("spreadsheets", {}).setdefault(spreadsheet_id, {})
	regions_cache = spreadsheet_cache.setdefault("regions", {})
	tab_regions = regions_cache.setdefault(tab_key, {})

	cached_region = tab_regions.get(sheets_range)
	region_expiry = cached_region.get("expiry") if cached_region else None

	if cached_region and region_expiry > time.time():
		tsprint(f"Cached region {sheets_range} found in spreadsheet {spreadsheet_id} tab {tab_name}")
		return cached_region["contents"]
	else:
		result = (
			sheets_service.spreadsheets()
			.values()
			.get(
				spreadsheetId=spreadsheet_id,
				range=sheets_range
			)
			.execute()
		)

		try:
			contents = result["values"]
		except KeyError: # if the region is empty, there's no values
			contents = []

		tsprint(f"Contents for region {sheets_range} retrieved. Caching.")


		tab_regions[sheets_range] = {
			"contents": contents,
			"expiry": time.time() + CACHE_COOLDOWN
		}

		return contents

def setup_sheets():
	"""
	Sets up a Google Sheet using the configuration provided.

	Returns:
		config_file: the config file that we created or opened
		sheets_service: the Google Sheets service we used
		spreadsheet: the spreadsheet gotten/created
		spreadsheet_id: the spreadsheet's id, for convenience
		tabs: the tabs listed in the config
	"""

	tsprint("Setting up Google Sheets.")

	# Log in using OAuth
	creds = do_oauth_flow()

	# verify that Google credentials file exists
	config.get_and_verify_config_data("oauth/google_credentials.json", False)

	config_name = "config/google_config.json"
	config_data = config.get_and_verify_config_data(config_name)

	sheets_service = None

	try:
		sheets_service = build("sheets", "v4", credentials=creds)
	except HttpError as error:
		tsprint(error)

	spreadsheet_id = config_data.get("id")
	spreadsheet = get_spreadsheet(
		sheets_service=sheets_service,
		spreadsheet_id=spreadsheet_id
	)
	tabs = config_data.get("tabs") # the listed tabs as a dict

	return config_data, sheets_service, spreadsheet, spreadsheet_id, tabs

if __name__ == "__main__":
	_, sheets_service, _, spreadsheet_id, tabs = setup_sheets("test")
	get_spreadsheet(sheets_service, spreadsheet_id)

	tsprint("")
	empty = is_spreadsheet_empty(sheets_service, spreadsheet_id)
	empty = is_spreadsheet_empty(sheets_service, spreadsheet_id)

	tsprint("")
	first_empty = find_first_empty_row(sheets_service, spreadsheet_id)
	first_empty = find_first_empty_row(sheets_service, spreadsheet_id)

	tsprint("")
	sheets_region = get_region(sheets_service, spreadsheet_id, tab_name="Logs")
	sheets_region = get_region(sheets_service, spreadsheet_id, tab_name="Logs")
	pass