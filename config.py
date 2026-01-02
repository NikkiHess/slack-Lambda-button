"""
Module for handling JSON configuration files.

Author:
Nikki Hess (nkhess@umich.edh)
"""

# built-in
from pathlib import Path
import os
import json

# my modules
from nikki_utils import tsprint

CONFIG_DEFAULTS_PATH = "config_defaults"

def get_and_verify_config_data(config_path: str, create_file: bool = True) -> dict:
    """
    Opens a config file based on its (relative or absolute) path. Optionally, opulates defaults if config not found.

    Args:
        config_path (str): the (relative or absolute) path of the config file to open
        create_file (bool): whether to create the file if it doesn't exist. default = True

    Returns:
        out (dict): the config's data
    """
    config_file = Path(config_path)
    tsprint(f'Getting/verifying config data for "{config_file.name}"')

    # get defaults from {config defaults path}/{config name}
    config_defaults_path = os.path.join(CONFIG_DEFAULTS_PATH, config_file.name)
    config_defaults = Path(config_defaults_path)
    if not config_defaults.exists():
        # only require defaults if we're creating a file
        if create_file:
            tsprint(f'ERROR: Defaults did not exist for "{config_file.name}". Turn off create_file or verify the defaults exist.')
            exit(1)
        
        # if not creating a file, just warn
        tsprint(f'WARNING: Defaults did not exist for "{config_file.name}". Assuming they are not needed.')
        config_defaults = None

    if create_file:
        config_file.parent.mkdir(parents=True, exist_ok=True) # make parent directory if needed
        config_file.touch(exist_ok=True) # make the file if needed

    # check for empty config file
    if os.stat(config_file).st_size == 0:
        tsprint(f'ERROR: Config file "{config_file.name}" was empty.')

        # write defaults if necessary
        if create_file:
            tsprint(f'Writing config defaults to "{config_file.name}"')
            config_file.write_text(config_defaults.read_text()) # could use json module, but this is easier
        
        tsprint(f'Please populate "{config_file.name} before running again.')

        exit(1)

    # check for malformed JSON
    try:
        config_data: dict = json.loads(config_file.read_text())
    except json.JSONDecodeError as e:
        tsprint(f'Config JSON was malformed for "{config_file.name}"')
        exit(1)

    # check for missing fields
    if create_file:
        tsprint(f'Checking for missing fields in config "{config_file.name}" from defaults.')
        config_defaults_data: dict = json.loads(config_defaults.read_text())
        missing_fields = [key for key in config_defaults_data.keys() if key not in config_data]
        if missing_fields:
            missing_fields_str = ", ".join(missing_fields)
            tsprint(f'Required fields were missing in "{config_file.name}": {missing_fields_str}')
            exit(1)
        
        tsprint("No missing fields found. Proceeding.")

    tsprint(f'Config file "{config_file.name}" loaded successfully.')
    return config_data

# TODO: apply this to every relevant config (file from config dir)