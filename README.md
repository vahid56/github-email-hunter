# 📧 GitHub Email Hunter

Find a GitHub user's public email by scanning their commits — no scraping, just the GitHub API.

```bash
uv run -m ghmail <username>
```

**Example**

```bash
uv run -m ghmail torvalds
```

**Output**

```text
[*] Fetching torvalds's repos...
[*] 42 repos found.
[*] Random repo: linux
[*] Random commit: 3f1a9c8b2e
[✓] Email found: someone@example.com
```

That's it. If an email is publicly exposed in any of the user's commits, this will likely find it. 🎯

---

## 🚀 Install

```bash
git clone https://github.com/vahid56/github-email-hunter
cd github-email-hunter
uv sync
uv run -m ghmail <username>
```

> Requires [uv](https://docs.astral.sh/uv/). It handles the environment and dependencies for you.

---

## 🔑 Recommended: add a token

Without a token, GitHub limits you to **60 requests/hour** — not enough for most users. Create a `.env` file in the project root:

```env
GITHUB_TOKEN=ghp_yourPersonalAccessTokenHere
```

No scopes needed. A plain token works fine for public data. ✅

---

## 🧠 Want to know more?

**How it works**

1. Fetches the user's public repos (paginated).
2. Picks random repos and random commits.
3. Downloads each commit's `.patch` file and extracts the first `Name <email>` header.
4. Skips GitHub's privacy addresses (`*.github.com`).
5. Returns the first real email it finds.

**Limits**

- 🔍 Checks up to **10 repos** and **5 commit pages per repo** — tunable in `find_email()` and `get_commits()`.
- 🕵️ Only works if the user's commits actually expose a real email. Many people hide theirs or use `users.noreply.github.com`.
- ⏱️ 0.5s delay between paginated requests when no token is set.

**Heads up**

This is an OSINT tool. Use it only on accounts you own or have permission to investigate. Respect GitHub's ToS and local privacy laws. ⚖️

---

## 📄 License

MIT — see [LICENSE](LICENSE).