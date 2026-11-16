# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-11-16

### Added

- The `dotdiff` command line tool, which compares two dotenv files and
  reports the variables that were added, removed or changed.
- A parser that reads `export`, single and double quotes, escapes, values
  that run over several lines and comments.
- `--json` for machine-readable output, `--mask` to hide the values, `--keys`
  for the key names alone and `--quiet` for the exit code alone.
- Exit codes: `0` when the files are the same, `1` when they differ and `2`
  when a file is missing or cannot be parsed.

[Unreleased]: https://github.com/v01dst/dotdiff/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/v01dst/dotdiff/releases/tag/v0.1.0
