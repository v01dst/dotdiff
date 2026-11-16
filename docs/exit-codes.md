# The exit codes

`dotdiff` always ends with one of three exit codes.

| Code | Meaning |
|---|---|
| `0` | the two files hold the same variables |
| `1` | the two files differ |
| `2` | a file is missing or cannot be parsed |

The codes follow the usual convention of the Unix tools, where `0` means the
command did what it was asked and anything else means it did not.

```bash
if dotdiff .env.local .env.production; then
    echo "the files are the same"
else
    echo "the files differ, or something went wrong"
fi
```

A missing file and a broken file both give `2`, so a script that only cares
about "are they the same" has to look at the code to tell the two apart.

The option `--quiet` prints nothing, so the exit code is the only output:

```bash
dotdiff --quiet .env.local .env.production
```

An unknown option or a missing file name also gives `2`, because that is
what the argument parser of Python uses.
