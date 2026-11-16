# The parser rules

`dotdiff` reads a dotenv file the way the common tools do, with a few
choices spelled out here.

## Lines

| Line | Result |
|---|---|
| `PORT=8080` | `PORT` is `8080` |
| `export PORT=8080` | the same, the `export` is dropped |
| `PORT = 8080` | the name and the value are trimmed |
| `PORT` | `PORT` is empty |
| `# a comment` | skipped |
| | skipped |
| `PORT=8080 # a note` | `PORT` is `8080` |

A name that appears twice keeps the last value. The order of the file is
kept, so the output reads like the file itself.

## Quotes

A value that starts with a quote runs until the matching quote, even when
that is on a later line:

```dotenv
PRIVATE_KEY="-----BEGIN KEY-----
line one
-----END KEY-----"
```

Inside double quotes the escapes `\n`, `\t`, `\r`, `\0`, `\\`, `\"`, `\'`
and `\$` are read. Every other backslash is kept as it is.

Inside single quotes nothing is escaped, so a Windows path stays a Windows
path:

```dotenv
WINDOWS_PATH='C:\Users\me'
```

## Comments

A `#` that follows a space ends a bare value:

```dotenv
A=value # a note
```

A `#` that is not preceded by a space stays part of the value, and a `#`
inside quotes is always part of the value.

## Names

A name may hold letters, digits, underscores and dots. It may not hold a
space, and it may not be empty. Both are reported with the line number.

## Errors

A file that cannot be read, a name that is empty or holds a space, and a
quote that is never closed all stop the tool with exit code `2`. The message
names the file and the line.
