# rtk output-compression hook

This project registers a `PreToolUse` hook (see `../settings.json`) that
transparently routes supported Bash commands through
[rtk](https://github.com/rtk-ai/rtk), a CLI proxy that strips 60-90% of the
noise out of verbose command output (git, npm/pnpm/yarn, pip, pytest, cargo,
docker, kubectl, aws, eslint, prettier, and more) before it reaches the
model's context window.

## How it works

`rtk-rewrite.sh` reads the Bash tool call Claude Code is about to run. If:

- the command's leading word is one of the supported tools, and
- the `rtk` binary is installed and on `PATH`,

it rewrites the command to `rtk <original command>` via the hook's
`updatedInput` field. Otherwise the command runs unchanged — the hook is a
no-op when `rtk` isn't installed, so nothing breaks if a contributor hasn't
set it up locally.

Compound commands (`&&`, `;`, `|`, subshells) are intentionally left
untouched to avoid mis-rewriting multi-step pipelines.

## Installing rtk locally

```bash
curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/master/install.sh | sh
rtk --version   # confirm it installed
```

No further setup is required — once `rtk` is on `PATH`, this repo's hook
picks it up automatically.
