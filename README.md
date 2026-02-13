# 🏁 FirstRun

**Contributor onboarding path verifier** — Prove every setup command in your docs actually works.

Stop losing contributors to broken `make dev-setup`, missing `.env.example`, and dead wiki links.

## Install

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Scan current repo
python cli.py scan .

# With link checking
python cli.py scan . --check-links

# CI mode: fail if score < 80, output SARIF
python cli.py scan . --min-score 80 --format sarif -o firstrun.sarif

# JSON output
python cli.py scan ./my-project --format json
```

## What It Checks

| Category | Example |
|---|---|
| **File references** | `.env.example` mentioned but doesn't exist |
| **Makefile targets** | `make dev-setup` in docs but not in Makefile |
| **npm scripts** | `npm run dev` but no `dev` script in package.json |
| **Dead links** | URLs returning 404 or unreachable |
| **Missing docs** | No README.md found at all |

## Output

```
🏁 FirstRun Contributor Readiness Score: 75/100

Found 3 issue(s):

  ❌ [command] README.md:12 — Makefile target `dev-setup` not found
  ⚠️ [file-ref] CONTRIBUTING.md:8 — Referenced file `.env.example` not found
  ⚠️ [dead-link] README.md:3 — URL returned 404: https://example.com/old-wiki
```

## Run Tests

```bash
pytest test_firstrun.py -v
```

## License

MIT
