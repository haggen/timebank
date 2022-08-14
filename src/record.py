# Useful when you're mixing database records and dicts.
class Record(dict):
    """
    Extends dict to support attribute-style access.
    """

    def __getattr__(self, name: str):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name: str, value: any):
        self[name] = value
