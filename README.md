<h1 align="center">📧 GitHub Email Hunter</h1>

<p align="center">
<img alt="licence-mit" src="https://img.shields.io/badge/license-MIT-green.svg">
<img alt="python-version" src="https://img.shields.io/badge/python-3.11%2B-blue.svg">
<img alt="pip-version" src="https://img.shields.io/badge/pip-ready-4BC51D.svg">
<img alt="uv-version" src="https://img.shields.io/badge/uv-ready-4BC51D.svg">
</p>

<p align="center">Find a GitHub user's public email by scanning their commits — no scraping, just the GitHub API.</p>

---

## 🚀 Install

Works with both `pip` and [uv](https://docs.astral.sh/uv/).

### With pip

```bash
git clone https://github.com/vahid56/github-email-hunter
cd github-email-hunter

# Option A — install the package (recommended)
pip install .

# Option B — only install dependencies, run from the repo
pip install -r requirements.txt
```

### With uv

```bash
git clone https://github.com/vahid56/github-email-hunter
cd github-email-hunter

# Option A — sync and install the package (recommended)
uv sync
uv run ghmail <username>

# Option B — ephemeral run, without syncing first
uv run ghmail <username>
```

> Both tools use the same `pyproject.toml`. `uv` additionally reads the
> committed `uv.lock` for fully reproducible installs.

---

## 📖 How to use?

Once installed, three entry points are available:

| Command                     | What it does                              |
| --------------------------- | ----------------------------------------- |
| `ghmail <username>`         | Installed console command (pip / uv)      |
| `python -m ghmail <username>` | Module entry point                      |
| `python ghmail.py <username>` | Legacy script (source checkout only)    |

**Example**

```bash
ghmail torvalds
```

**Output**

```text
┌───────────────────────────  GitHub Email Hunter  ───────────────────────────┐
│      Target  torvalds                                                       │
│       Token  not provided — 60 requests/hour                                │
│       Repos  10                                                             │
│Commit pages  5                                                              │
└────────────────────────────────── v0.1.0 ───────────────────────────────────┘
  • Fetching public repositories for torvalds
  • Scanning 3 of 12 repositories
  • [1/3] Checking repository: uemacs
  ✓ Email found: torvalds@linux-foundation.org

┌───────────────────────────────  Email found  ───────────────────────────────┐
│   Email  torvalds@linux-foundation.org                                      │
│  Target  torvalds                                                           │
│    Repo  uemacs                                                             │
│  Commit  e8f984a1b0                                                         │
│  Source  https://github.com/torvalds/uemacs/commit/e8f984a1b0.patch         │
└─────────────────────────────────────────────────────────────────────────────┘
```

That's it. If an email is publicly exposed in any of the user's commits, this
will likely find it. 🎯

### Options

```text
usage: ghmail [-h] [-n N] [-p N] [-t SEC] [-v] [--token TOKEN] [--version]
              USERNAME

positional arguments:
  USERNAME              GitHub username to investigate

options:
  -h, --help            show this help message and exit
  -n N, --max-repos N   maximum number of repositories to inspect (0 = all)
                        (default: 10)
  -p N, --max-commit-pages N
                        maximum pages of commits to fetch per repository
                        (default: 5)
  -t SEC, --timeout SEC HTTP request timeout in seconds (default: 15)
  -v, --verbose         print debug diagnostics
  --token TOKEN         GitHub token; overrides the GITHUB_TOKEN environment
                        variable
  --version             show program's version number and exit
```

---

## 🔑 Recommended: add a token

Without a token, GitHub limits you to **60 requests/hour** — not enough for
most users. Create a `.env` file in the project root:

```env
GITHUB_TOKEN=ghp_yourPersonalAccessTokenHere
```

or pass it directly:

```bash
ghmail torvalds --token ghp_yourPersonalAccessTokenHere
```

No scopes needed. A plain token works fine for public data. ✅

---

## 🧠 Want to know more?

**How it works**

1. Fetches the user's public repos (paginated).
2. Picks random repos and random commits.
3. Downloads each commit's `.patch` file and reads its `From:` header.
4. Skips GitHub's privacy addresses (`*.github.com`, e.g. `users.noreply.github.com`).
5. Returns the first real email it finds.

**Limits**

- 🔍 Checks up to **10 repos** and **5 commit pages per repo** by default —
  tunable with `--max-repos` and `--max-commit-pages`.
- 🕵️ Only works if the user's commits actually expose a real email. Many people
  hide theirs or use `users.noreply.github.com`.
- ⏱️ 0.5s delay between paginated requests when no token is set.

**Heads up**

This is an OSINT tool. Use it only on accounts you own or have permission to
investigate. Respect GitHub's ToS and local privacy laws. ⚖️

---

## 🛠️ Development

```bash
uv sync                 # create the environment and lock dependencies
uv run ghmail torvalds  # run the tool
uv build                # build sdist + wheel into dist/
```

## 📄 License

MIT — see [LICENSE](LICENSE).