# dotdiff

Compare two dotenv files and see what changed. Zero dependencies, pure Python
standard library.

## Why

A `.env` file is a pile of secrets that everybody edits by hand. When the
production file drifts away from the local one, nothing points at the line
that changed until the app breaks in a way nobody can explain.

`dotdiff` reads two dotenv files and tells you which keys were added, which
were removed and which ones hold a different value.

## Install

```bash
pip install dotdiff
```

Or run it without installing anything:

```bash
python dotdiff.py .env.local .env.production
```

## Usage

```bash
dotdiff OLD NEW
```

```
2 changes between .env.local and .env.production

+ NEW_FEATURE_FLAG=enabled
~ PORT=8080 -> 9090
```

The exit code carries the answer, so a script can branch on it:

| Exit code | Meaning |
|---|---|
| `0` | the files hold the same variables |
| `1` | the files differ |
| `2` | a file is missing or cannot be parsed |

## Options

| Option | What it does |
|---|---|
| `--json` | print the result as JSON |
| `--mask` | replace every value with `***` |
| `--keys` | print key names only, no values |
| `-q`, `--quiet` | print nothing, use the exit code |

## Read more

- [The parser rules](docs/parser.md)
- [The exit codes](docs/exit-codes.md)

## License

MIT.
