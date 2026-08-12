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
- `finance-steward` runs its standard-library importer with `uv run python`;
  install [`uv`](https://docs.astral.sh/uv/) on the agent runtime's `PATH`.

`finance-steward` is self-contained under
`skills/finance/finance-steward/`, so an agent such as OpenClaw can sync that
directory directly into its workspace `skills/finance-steward/` directory.
