# Useful when you're mixing database records and dicts.
class Record(dict):
    """
    Extends dict to support attribute-style access.
    """

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key, value):
        self[key] = value
