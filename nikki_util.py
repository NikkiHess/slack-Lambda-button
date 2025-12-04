#!/usr/bin/env python3

"""
Just utils for me.

Author:
Nikki Hess (nkhess@umich.edu)
"""

from datetime import datetime
from ctypes import cdll, byref, create_string_buffer
from pathlib import Path

LOG_FILE = None

def get_datetime(long: bool = True, filesafe: bool = False, include_time: bool = True) -> str | None:
    """
    Gets the current datetime as a beautifully formatted string

    ## Args:
    - `long` (bool): whether to have a long datetime or a short one
    - `filesafe` (bool): whether to keep the output safe for filenames (replace "/" and ":" with "-")
    - `include_time` (bool): whether to include the time
    
    ## Returns:
    - `formatted_time` (str | None): the formatted time string, if present
    """
    formatted_time = None
    current_time = datetime.now()
    
    if long:
        time_str = " %I:%M:%S %p"
        formatted_time = current_time.strftime("%B %d, %Y " + (time_str if include_time else ""))
    else:
        formatted_time = current_time.strftime("%x" + (" %X" if include_time else ""))

    if filesafe:
        formatted_time = formatted_time.replace("/", "-").replace(":", "-")

    return formatted_time

def create_logfile(dir_path: str = "logs/", include_time: bool = True):
    """
    Creates the logfile in logs/{datetime}.log

    ## Args:
    - `dir_path` (str): the path to the dir where we are saving logfiles
    - `include_time` (bool): whether to include the time
    """
    global LOG_FILE

    formatted_time = get_datetime(long=False, filesafe=True, include_time=include_time)
    LOG_FILE = Path(f"{dir_path}/{formatted_time}.log")
    Path(dir_path).mkdir(exist_ok=True)
    LOG_FILE.touch(exist_ok=True) # it shouldn't exist, but just in case it does for some reason :)


def tsprint(message: str, log: bool = True):
    """
    Prints with date (e.g. "[9/18/2025 15:16:25] message here")

    ## Args:
    - `message` (str): the message to print
    - `log` (bool): whether to log to the log file. on by default
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

def set_process_name(process_name: str = b"SLB-GUI\x00"):
    """
    Adapated from https://stackoverflow.com/questions/51521320/tkinter-python-how-to-give-process-name
    
    ## Args:
    - `process_name` (str): the null (\\x00) terminated name to set the process to
    """

    import platform
    # only on Linux
    if platform.system() == "Linux":
        process_name = process_name + b"\x00"

        libc = cdll.LoadLibrary('libc.so.6')  # Loading a 3rd party library C
        buff = create_string_buffer(len(process_name)+1)  # Note: One larger than the name (man prctl says that)
        buff.value = process_name

        libc.prctl(15, byref(buff), 0, 0, 0)