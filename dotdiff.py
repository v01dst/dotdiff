"""Read dotenv files and compare two of them."""

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
