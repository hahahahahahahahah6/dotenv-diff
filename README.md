# dotenv-diff

Diff `.env` against `.env.example` and catch missing keys **before** deploy, not after.

## The pain

It works on your machine. You deploy. First real request hits the endpoint and the app 500s — because `STRIPE_WEBHOOK_SECRET` was never set in production. Somebody added the key to `.env.example` three PRs ago, you pulled it, ran the code locally with your own `.env`, and never noticed the mismatch. Every deploy checklist has a line that says "did you update the env vars?" and nobody ever reads it.

`dotenv-diff` turns that checklist line into a command. Put it in CI, in a pre-commit hook, in your deploy script:

```bash
dotenv-diff || echo "env mismatch — abort deploy"
```

## Install

No dependencies, stdlib only, Python 3.9+.

```bash
curl -O https://raw.githubusercontent.com/hahahahahahahahah6/dotenv-diff/main/dotenv_diff.py
chmod +x dotenv_diff.py
```

Or clone the repo and run `python3 dotenv_diff.py`.

## Usage

```bash
dotenv-diff [.env] [.env.example] [--json] [--strict]
```

Defaults are `.env` and `.env.example`. Pass `-` for either side to read from stdin.

### Example

`.env.example` says your app needs four keys. Your `.env` was last touched a month ago:

```bash
$ dotenv-diff
ERRORS:
  [missing] STRIPE_WEBHOOK_SECRET

WARNINGS:
  [extra] LEGACY_MAILGUN_KEY
  [placeholder] DATABASE_URL (value: 'postgres://changeme@localhost/db')

1 error(s), 2 warning(s)
$ echo $?
1
```

Findings:

| Level | Code          | Meaning |
|-------|---------------|---------|
| ERROR | `missing`     | Key is in the example but absent from `.env` |
| WARN  | `extra`       | Key is in `.env` but not in the example (stale or renamed?) |
| WARN  | `empty`       | Key is present but its value is empty |
| WARN  | `placeholder` | Value looks like an unfilled placeholder (`your_`, `xxx`, `changeme`, `<...>`, `example`, `todo`…) |

Exit codes: **0** if clean, **1** if any ERROR. `--strict` also exits 1 on warnings — that's the mode you want in CI. `--json` emits machine-readable findings.

Parsing handles `KEY=value`, `export KEY=value`, single/double quotes, `#` comments and blank lines.

## Differentiation

This is **not a secret manager**. It doesn't encrypt, sync, or rotate anything. It's a ~200-line pre-deploy gate: it answers one question — *does the env this code runs with match the env the code was written against?*

Tools like [direnv](https://direnv.net/) load your `.env` into the shell; they trust whatever file you give them. `dotenv-diff` checks that the file itself is complete before direnv ever sees it. Use both: dotenv-diff validates, direnv loads.

## License

MIT — see [LICENSE](LICENSE).
