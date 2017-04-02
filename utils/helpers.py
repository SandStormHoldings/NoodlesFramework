def path_agnostic(possible_paths):
    """
    Depends on: os
    Requires: possible_paths as a list
    Description: Check every path in a list and return the first path
                 that is really exists
    Example: path_agnostic([ '/usr/bin/chromedriver2',
                             '/usr/local/bin/chromedriver' ])
    """
    import os

    for path in possible_paths:
        if os.path.exists(path):
            return path

    raise Exception('there is no valid path in list: %s' % str(possible_paths))

def get_config(variable_name, default=None,ignore_import_errors=False):
    """
    Depends on: local_config, config
    Requires: variable_name as a str
    Returns: the value of variable
    Description: Ask the variable from local_config, if the variable
                 is not defined in local_config - request variable from config
    Example: get_config('VARIABLE_NAME')
    """
    try:
        import config
        import local_config
    except ImportError:
        if ignore_import_errors:
            return None
        else:
            raise

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


def is_ws_error_abnormal(exc):
    from geventwebsocket.websocket import MSG_ALREADY_CLOSED, MSG_SOCKET_DEAD
    message = exc.message
    return message != MSG_SOCKET_DEAD and message != MSG_ALREADY_CLOSED and 'closed' not in message.lower()\
        and 'dead' not in message.lower()
