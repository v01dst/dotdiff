"""Read dotenv files and compare two of them."""

import json
import sys

EXIT_SAME = 0
EXIT_DIFFERENT = 1
EXIT_ERROR = 2

UNESCAPE = {
    "n": "\n",
    "t": "\t",
    "r": "\r",
    "0": "\0",
    "\\": "\\",
    '"': '"',
    "'": "'",
    "$": "$",
}


class DotenvError(ValueError):
    """Raised when a dotenv file cannot be read."""


class Entry:
    """One variable of a dotenv file."""

    __slots__ = ("key", "value", "line")

    def __init__(self, key, value, line):
        self.key = key
        self.value = value
        self.line = line

    def __repr__(self):
        return "Entry(%r, %r, %r)" % (self.key, self.value, self.line)


def _check_key(key, path, line):
    if not key:
        raise DotenvError("%s:%d: the variable name is empty" % (path, line))
    if any(character.isspace() for character in key):
        raise DotenvError(
            "%s:%d: the variable name %r holds a space" % (path, line, key)
        )


def _find_closing(body, quote, escapes):
    position = 0
    length = len(body)
    while position < length:
        character = body[position]
        if escapes and character == "\\":
            position += 2
            continue
        if character == quote:
            return position
        position += 1
    return -1


def _unescape(raw):
    pieces = []
    index = 0
    length = len(raw)
    while index < length:
        character = raw[index]
        if character == "\\" and index + 1 < length:
            following = raw[index + 1]
            if following in UNESCAPE:
                pieces.append(UNESCAPE[following])
                index += 2
                continue
        pieces.append(character)
        index += 1
    return "".join(pieces)


def _read_quoted(text, quote, lines, index, path, line, escapes):
    body = text[1:]
    pieces = []
    while True:
        closing = _find_closing(body, quote, escapes)
        if closing >= 0:
            pieces.append(body[:closing])
            break
        pieces.append(body)
        pieces.append("\n")
        if index >= len(lines):
            raise DotenvError(
                "%s:%d: the quoted value is never closed" % (path, line)
            )
        body = lines[index]
        index += 1
    raw = "".join(pieces)
    return (_unescape(raw) if escapes else raw), index


def _read_bare(text):
    marker = text.find(" #")
    if marker >= 0:
        text = text[:marker]
    return text.strip()


def _read_value(text, lines, index, path, line):
    value = text.strip()
    if value.startswith("'"):
        return _read_quoted(value, "'", lines, index, path, line, False)
    if value.startswith('"'):
        return _read_quoted(value, '"', lines, index, path, line, True)
    return _read_bare(value), index


def parse(text, path="<string>"):
    """Read the variables of a dotenv file and return them in file order."""
    entries = {}
    lines = text.splitlines()
    index = 0
    total = len(lines)
    while index < total:
        raw = lines[index]
        line = index + 1
        index += 1
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[len("export ") :].lstrip()
        if "=" not in stripped:
            key = stripped.strip()
            _check_key(key, path, line)
            entries[key] = Entry(key, "", line)
            continue
        key, _, rest = stripped.partition("=")
        key = key.strip()
        _check_key(key, path, line)
        value, index = _read_value(rest, lines, index, path, line)
        entries[key] = Entry(key, value, line)
    return entries


def read_file(path):
    """Read a dotenv file and return its text."""
    if path == "-":
        return sys.stdin.read()
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as handle:
            return handle.read()
    except OSError as error:
        raise DotenvError("%s: %s" % (path, error.strerror or error)) from error


def compare(left, right):
    """Compare two parsed files and return the differences between them."""
    added = []
    removed = []
    changed = []
    unchanged = []
    for key, entry in right.items():
        previous = left.get(key)
        if previous is None:
            added.append(entry)
        elif previous.value != entry.value:
            changed.append((previous, entry))
        else:
            unchanged.append(key)
    for key, entry in left.items():
        if key not in right:
            removed.append(entry)
    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "unchanged": unchanged,
    }


def is_identical(differences):
    """True when two parsed files hold the same variables."""
    return not (
        differences["added"] or differences["removed"] or differences["changed"]
    )


def _one_line(value):
    return value.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")


def build_result(left_name, right_name, left, right, mask=False, keys_only=False):
    """Turn the difference between two files into a result that can be shown."""
    differences = compare(left, right)

    def shown(value):
        if keys_only:
            return None
        if mask:
            return "***"
        return value

    added = [{"key": entry.key, "value": shown(entry.value)} for entry in differences["added"]]
    removed = [
        {"key": entry.key, "value": shown(entry.value)}
        for entry in differences["removed"]
    ]
    changed = [
        {
            "key": before.key,
            "left": shown(before.value),
            "right": shown(after.value),
        }
        for before, after in differences["changed"]
    ]
    return {
        "left": left_name,
        "right": right_name,
        "identical": is_identical(differences),
        "added": added,
        "removed": removed,
        "changed": changed,
        "unchanged": list(differences["unchanged"]),
    }


def render_text(result, keys_only=False):
    """Turn a result into the lines that are printed on the terminal."""
    added = result["added"]
    removed = result["removed"]
    changed = result["changed"]
    total = len(added) + len(removed) + len(changed)
    if result["identical"]:
        return "No differences between %s and %s" % (result["left"], result["right"])
    header = "%d change%s between %s and %s" % (
        total,
        "" if total == 1 else "s",
        result["left"],
        result["right"],
    )
    lines = [header, ""]
    for entry in added:
        lines.append(_line_added(entry, keys_only))
    for entry in changed:
        lines.append(_line_changed(entry, keys_only))
    for entry in removed:
        lines.append(_line_removed(entry, keys_only))
    return "\n".join(lines)


def _line_added(entry, keys_only):
    if keys_only:
        return "+ %s" % entry["key"]
    return "+ %s=%s" % (entry["key"], _one_line(entry["value"]))


def _line_changed(entry, keys_only):
    if keys_only:
        return "~ %s" % entry["key"]
    return "~ %s=%s -> %s" % (
        entry["key"],
        _one_line(entry["left"]),
        _one_line(entry["right"]),
    )


def _line_removed(entry, keys_only):
    if keys_only:
        return "- %s" % entry["key"]
    return "- %s=%s" % (entry["key"], _one_line(entry["value"]))


def render_json(result):
    """Turn a result into JSON."""
    return json.dumps(result, indent=2)
