# Skills

Personal agent skills, installable via [`npx skills`](https://github.com/vercel-labs/skills) into any supported agent (Claude Code, and others `npx skills` targets).

## Install

```bash
npx skills add zhhailon/skills
```

## Structure

```
skills/
  finance/        # private household finance import, validation, and analysis
  obsidian/       # vault-specific skills, only fire when working in Obsidian
  productivity/   # general-purpose skills
```

The installer flattens directory nesting and uses each `SKILL.md`'s `name:`
field as the installed id — it does not read the category folder. Obsidian
skills are named `obsidian-<x>` in frontmatter for that reason, so the
namespace survives install even though the folder doesn't.

## Runtime requirements

- Obsidian skills require the `obsidian` CLI on `PATH`.
- `finance-steward` uses whatever LLM the runtime already provides for
  extraction — it names no model or provider. Its `scripts/finance.py`
  (`stage` and `load` subcommands) imports only the standard library, so it
  needs Python 3.9+ on `PATH` and no package manager, virtual environment, or
  installed dependency. The ledger it writes needs SQLite 3.37+, because the
  schema uses `STRICT` tables.

`finance-steward` is self-contained under `skills/finance/finance-steward/`,
so any agent runtime can sync that directory directly into its workspace
`skills/finance-steward/` directory.
