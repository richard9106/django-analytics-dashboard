"""Only structural error diagnostics may leave the application."""
import re
from pathlib import PurePath

_IDENTIFIER = re.compile(r'^[A-Za-z_][A-Za-z0-9_.<>]{0,120}$')


def before_send(event, hint):
    values = []
    for item in (event.get('exception') or {}).get('values', []):
        name = item.get('type', 'Error')
        if not isinstance(name, str) or not _IDENTIFIER.fullmatch(name):
            name = 'Error'
        frames = []
        for frame in (item.get('stacktrace') or {}).get('frames', []):
            clean = {}
            filename = frame.get('filename')
            if isinstance(filename, str):
                basename = PurePath(filename).name
                if re.fullmatch(r'[A-Za-z0-9_.-]+\.(py|js)', basename):
                    clean['filename'] = basename
            function = frame.get('function')
            if isinstance(function, str) and _IDENTIFIER.fullmatch(function):
                clean['function'] = function
            if isinstance(frame.get('lineno'), int):
                clean['lineno'] = frame['lineno']
            if clean:
                frames.append(clean)
        values.append({'type': name, 'value': '[message withheld]', 'stacktrace': {'frames': frames}})
    if not values:
        return None  # Arbitrary log messages may contain clinical or credential data.
    clean = {key: event[key] for key in ('event_id', 'timestamp', 'platform', 'level') if key in event}
    clean['exception'] = {'values': values}
    return clean


def discard_transaction(event, hint):
    return None


def discard_breadcrumb(crumb, hint):
    return None
