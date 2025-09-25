#!/usr/bin/env python3

"""
Just utils for me.

Author:
Nikki Hess (nkhess@umich.edu)
"""

from datetime import datetime
import requests
from pathlib import Path

LOG_FILE = Path("program.log")
LOG_FILE.open("w", encoding="utf-8").close()

def timestamp_print(message: str, log: bool = True):
    """
    Prints with date (e.g. "[9/18/2025 15:16:25] message here")

    Args:
        message (str): the message to print
        log (bool): whether to log to the log file. on by default
    """

    now = get_datetime(long=False)
    output = f"[{now}] {message}"
    print(output)

    if log:
        try:
            with LOG_FILE.open("a", encoding="utf-8") as file:
                file.write(output + "\n")
        except Exception as e:
            print(f"[{now}] Failed to write to log file: {e}")


def get_datetime(long: bool = True) -> str | None:
    """
    Gets the current datetime as a beautifully formatted string

    Args:
        long (bool): whether to have a long datetime or a short one
    
    Returns:
        formatted_time (str | None): the formatted time string, if present
    """
    formatted_time = None
    current_time = datetime.now()
    
    if long:
        formatted_time = current_time.strftime("%B %d, %Y %I:%M:%S %p")
    else:
        formatted_time = current_time.strftime("%x %X")

    return formatted_time