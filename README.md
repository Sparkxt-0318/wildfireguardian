# Autonomous Web Agency

A Claude Code project that finds local businesses without websites, builds each one a
bespoke site from their **real** photos and details, deploys it to a private URL, and drafts
a personalised pitch — looping on autopilot. It mirrors the **find → gather → build →
outreach** pipeline and runs under a single Claude Code session via `/run <region>`.

> This is a **v1 scaffold**. The deterministic plumbing (discovery, scraping, CRM, deploy,
> sending) is production-shaped. The *design quality* of generated sites and the
> *deliverability* of outreach are where you iterate — that's the hard, valuable part.

## What you need

- **Claude Code** (Max plan recommended for build quality) — runs the agent.
- **Google Maps Platform API key** with **Places API (New)** enabled — discovery + photos.
- **Vercel account + token** (free tier) — hosting.
- **An email path** *(optional for v1)* — a Resend API key **or** SMTP creds. Leave unset to
  stay fully dry-run (drafts written to disk, nothing sent).
- Node 22.15+, Python 3.10+.

## Setup (~10 min)

```bash
cp .env.example .env          # then fill in your keys
pip install -r requirements.txt
python -m playwright install chromium
npm install                   # installs the Vercel CLI locally
python scripts/crm.py init    # create the CRM
npx vercel login              # one-time (or rely on VERCEL_TOKEN in .env)
```

## Run it

Open this folder in Claude Code and run:

```
/run Cambridge, UK
```

Claude will find businesses, gather their data, build + deploy sites, and draft pitches,
looping until you stop it. Check progress any time:

```bash
python scripts/crm.py status
```

## Run a single stage by hand

```bash
python scripts/find.py "Cambridge, UK" --categories plumber electrician
python scripts/gather.py                                  # next 'new' lead
# (Claude builds the site into data/gathered/<slug>/site/)
python scripts/screenshot.py data/gathered/<slug>/site/index.html
python scripts/deploy.py data/gathered/<slug>/site
```

## Sending & compliance

Outreach is **DRY_RUN by default** — drafts go to `data/outbox/`, nothing is sent. Only set
`DRY_RUN=false` once you've handled email compliance: a sender domain you control, a real
physical address, a working unsubscribe path, and sane volume. Unsolicited commercial email
is regulated (CAN-SPAM, PECR/GDPR, PIPA, etc.).

Sites are also built **on spec** at a private, unguessable URL. The owner is never on the
hook for anything until they reply yes; if they decline, take the deployment down.

## Layout

| Path | What it is |
|------|------------|
| `CLAUDE.md` | The operating manual the agent follows |
| `scripts/` | `find`, `gather`, `crm`, `screenshot`, `deploy`, `send_email` |
| `skills/build-site/` | How the agent designs + builds each site |
| `skills/outreach/` | How the agent writes each pitch |
| `templates/site-base/` | Minimal fallback skeleton (build bespoke, don't fill in) |
| `data/` | CRM + generated sites + outbox (created at runtime, git-ignored) |
| `.claude/commands/run.md` | The `/run` command |
