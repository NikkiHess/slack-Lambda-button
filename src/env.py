# built-in
import os

# pypi
from py_dotenv import read_dotenv

read_dotenv()

def get_env(key: str) -> (str | None):
    """
    Gets an environment variable

	:param config_path: the (relative or absolute) path of the config file to open
	:type config_path: str

	:param create_file: whether to create the file if it doesn't exist. default = True
	:type create_file: bool

	:return: the config's data
	:rtype: dict
    """
    return os.getenv(key)