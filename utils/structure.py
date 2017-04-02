"""
Convert dict request to object
"""


class Structure(object):
    def __init__(self, entries):
        self.entries = entries

    def __getattr__(self, name):
        value = self.entries.get(name)
        if value is not None:
            if type(value) == dict:
                return Structure(value)
            return value
        else:
            return None

    def get(self, key, default=False):
        return self.entries.get(key, default)
