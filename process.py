from ctypes import cdll, byref, create_string_buffer
import platform

def set_process_name_linux(process_name: str = b"SLB-GUI\x00"):
    """
    Adapated from https://stackoverflow.com/questions/51521320/tkinter-python-how-to-give-process-name
    
    ## Args:
    - `process_name` (str): the null (\\x00) terminated name to set the process to
    """

    # only on Linux
    if platform.system() == "Linux":
        process_name = process_name + b"\x00"

        libc = cdll.LoadLibrary('libc.so.6')  # Loading a 3rd party library C
        buff = create_string_buffer(len(process_name)+1)  # Note: One larger than the name (man prctl says that)
        buff.value = process_name

        libc.prctl(15, byref(buff), 0, 0, 0)