#!/usr/bin/env python3
"""dotenv-diff: diff .env against .env.example and catch missing keys before deploy.

Usage:
    dotenv-diff [.env] [.env.example] [--json] [--strict]

Exit codes: 0 = clean, 1 = ERROR findings (missing keys); with --strict,
warnings also exit 1.
"""

import argparse
import json
import re
import sys

VERSION = "0.1.0"

# Placeholder fragments (case-insensitive substring match against the value).
_PLACEHOLDER_RE = re.compile(
    r"(your_|your-|changeme|\bxxx+\b|example|todo|placeholder|replace.?me|"
    r"fill.?me|insert.?here|\.\.\.|^<$)",
    re.IGNORECASE,
)


def strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def strip_inline_comment(value: str) -> str:
    """Strip a trailing ' # comment' that appears outside of quotes.

    A '#' inside single/double quotes is part of the value; without a
    preceding space it is also kept (e.g. 'a#b' is a valid value).
    """
    quote = None
    for i, ch in enumerate(value):
        if quote:
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
        elif ch == "#" and (i == 0 or value[i - 1] in (" ", "\t")):
            return value[:i].rstrip()
    return value


def parse_dotenv(text: str) -> dict:
    """Parse KEY=value pairs. Returns dict of KEY -> raw value (unquoted)."""
    result = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        # Inline comment support: strip trailing ' # ...' outside quotes.
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            continue
        value = strip_quotes(strip_inline_comment(value.strip()).strip())
        result[key] = value
    return result


def is_placeholder(value: str) -> bool:
    v = value.strip()
    if not v:
        return False
    if re.search(r"<[^<>]*>", v):  # <your-key-here>, <secret>
        return True
    return bool(_PLACEHOLDER_RE.search(v))


def diff(env: dict, example: dict) -> list:
    findings = []
    for key in sorted(example):
        if key not in env:
            findings.append({"level": "error", "code": "missing", "key": key,
                             "message": f"missing key: {key} is in the example but not in .env"})
        elif env[key] == "":
            findings.append({"level": "warning", "code": "empty", "key": key,
                             "message": f"empty value: {key} is present but has no value"})
        elif is_placeholder(env[key]):
            findings.append({"level": "warning", "code": "placeholder", "key": key,
                             "value": env[key],
                             "message": f"placeholder: {key} looks like an unfilled placeholder"})
    for key in sorted(env):
        if key not in example:
            findings.append({"level": "warning", "code": "extra", "key": key,
                             "message": f"extra key: {key} is in .env but not in the example"})
    return findings


def read_source(path: str, default: str) -> str:
    if path == "-":
        return sys.stdin.read()
    if path is None:
        path = default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"dotenv-diff: file not found: {path}", file=sys.stderr)
        sys.exit(2)


def render_text(findings: list) -> None:
    errors = [f for f in findings if f["level"] == "error"]
    warnings = [f for f in findings if f["level"] == "warning"]
    if not findings:
        print("dotenv-diff: clean — .env matches .env.example")
        return
    if errors:
        print("ERRORS:")
        for f in errors:
            print(f"  [missing] {f['key']}")
        print()
    if warnings:
        print("WARNINGS:")
        for f in warnings:
            suffix = f" (value: {f['value']!r})" if "value" in f else ""
            print(f"  [{f['code']}] {f['key']}{suffix}")
        print()
    print(f"{len(errors)} error(s), {len(warnings)} warning(s)")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="dotenv-diff",
        description="Diff .env against .env.example and catch missing keys before deploy.")
    parser.add_argument("env_file", nargs="?", default=".env",
                        help="path to .env (default: .env); '-' reads stdin")
    parser.add_argument("example_file", nargs="?", default=".env.example",
                        help="path to .env.example (default: .env.example); '-' reads stdin")
    parser.add_argument("--json", action="store_true", help="emit findings as JSON")
    parser.add_argument("--strict", action="store_true",
                        help="exit 1 on warnings too")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    args = parser.parse_args(argv)

    env = parse_dotenv(read_source(args.env_file, ".env"))
    example = parse_dotenv(read_source(args.example_file, ".env.example"))
    findings = diff(env, example)

    if args.json:
        print(json.dumps(findings, indent=2))
    else:
        render_text(findings)

    errors = any(f["level"] == "error" for f in findings)
    warnings = any(f["level"] == "warning" for f in findings)
    if errors or (args.strict and warnings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
