from ctypes import cdll, byref, create_string_buffer
from nikki_utils import tsprint
import platform

def set_process_name_linux(process_name: str = b"SLB-GUI\x00"):
    """
    Adapated from https://stackoverflow.com/questions/51521320/tkinter-python-how-to-give-process-name
    :param process_name: the null (\x00) terminated byte-string name to set the process to
    :type process_name: bytes
    """

    tsprint("set_process_name_linux called.")

    # only on Linux
    if platform.system() == "Linux":
        tsprint("Platform is Linux. Attempting to set process name.")
        process_name = process_name + b"\x00"

        libc = cdll.LoadLibrary('libc.so.6')  # Loading a 3rd party library C
        buff = create_string_buffer(len(process_name)+1)  # Note: One larger than the name (man prctl says that)
        buff.value = process_name

        try:
            libc.prctl(15, byref(buff), 0, 0, 0)
            tsprint("Process name set to {process_name}.")
        except Exception as e:
            tsprint(f"ERROR: Failed to set process name: {e}")
    else:
        tsprint("Platform is not Linux. Skipping setting process name.")