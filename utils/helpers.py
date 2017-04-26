import config
import local_config


def get_config(variable_name, default=None):
    """
    Depends on: local_config, config
    Requires: variable_name as a str
    Returns: the value of variable
    Description: Ask the variable from local_config, if the variable
                 is not defined in local_config - request variable from config
    Example: get_config('VARIABLE_NAME')
    """
    if hasattr(local_config, variable_name):
        return getattr(local_config, variable_name)
    elif hasattr(config, variable_name):
        return getattr(config, variable_name)
    else:
        return default


def is_ascii(string):
    if not string:
        return
    return all(ord(c) < 128 for c in string)
