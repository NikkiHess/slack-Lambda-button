# Duderstadt Center Help Buttons

This repository contains the code for running the Raspberry Pi Help Buttons at the Duderstadt center. Clicking or tapping the screen triggers an AWS-backed workflow that posts a message to Slack and records events in Google Sheets.

## Overview
- **Summary:** A small Python project that integrates a physical button (device) with AWS Lambda and Slack. When the button is pressed, the system posts a message to a configured Slack channel and logs events in Google Sheets. It has two main use-cases:
  1. **Guest Help**: Allows guests or visitors to request assistance.
  2. **Staff Assistance**: Acts as an internal signaling system, especially when staff members find themselves in situations where they might need immediate help from another adult on-site.
- **Local Modules:** `gui.py`, `slack.py`, `aws.py`, `sheets.py`, `process.py`.
- **Remote Modules:**  `lambda_function.py`

## Prerequisites
- Python 3.14+
- AWS account + credentials with permissions for Lambda, SQS, and CloudWatch
- Slack app with a bot token (bot OAuth token) and permissions to post messages
- Google API credentials for Sheets (stored in `oauth/`)

## Installation
1. Create and activate a virtual environment (recommended):

    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

2. Install dependencies (in order):

- OS-Specific Dependencies
  - Linux
    ```bash
    sudo apt-get install -y python3-dev libasound2-dev
    ```

- Universal Dependencies

  ```bash
  pip install --upgrade -r requirements.txt
  ```

3. Create and fill out configuration files (see config_defaults directory for required values)
- `config/slack.json`: Slack app settings
- `config/button.json`: Device settings
- `config/aws.json`: AWS-related settings
- `config/google_config.json`: Google Sheets config (spreadsheet id, tabs, etc.).

4. Get credentials from Google Cloud + place in `oauth/` folder.

Staff members can also configure the functionality of each button on the relevant Google Sheet (defined in `google_config.json`)

## Running Locally
- To run the GUI:

  ```bash
  python gui.py
  ```

## Packaging For Lambda
Packaging
```bash
# Install Python Requests library
pip install --target ./package --upgrade -r requirements-aws.txt

# Copy config over to package, if it exists
copy config ./package/config
```

## Troubleshooting
- Check `logs/` for runtime logs and error traces.

# License
- MIT License. See `LICENSE` in the repository root for more details.

# Contact
- Maintainer: Nikki Hess (nkhess@umich.edu)