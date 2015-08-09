from __future__ import unicode_literals


def int_or_None(value):
    if value:
        try:
            return int(value)
        except ValueError:
            return None
    return None
