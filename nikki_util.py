#!/usr/bin/env python3

"""
Just utils for me.

Author:
Nikki Hess (nkhess@umich.edu)
"""

from datetime import datetime
from ctypes import cdll, byref, create_string_buffer
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

def set_process_name(process_name: str = b"SLB-GUI\x00"):
    """
    Adapated from https://stackoverflow.com/questions/51521320/tkinter-python-how-to-give-process-name
    
    Args:
        process_name (str): the null (\\x00) terminated name to set the process to
    """

    import os
    if os.name == "posix":
        process_name = process_name + b"\x00"

        libc = cdll.LoadLibrary('libc.so.6')  # Loading a 3rd party library C
        buff = create_string_buffer(len(process_name)+1)  # Note: One larger than the name (man prctl says that)
        buff.value = process_name  # Null terminated string as it should be

        libc.prctl(15, byref(buff), 0, 0, 0)
        # Refer to "#define" of "/usr/include/linux/prctl.h" for the mysterious value 16 & arg[3..5] are zero as the man page says.