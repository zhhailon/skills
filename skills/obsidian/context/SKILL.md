---
name: obsidian-context
description: Obsidian vault skill. Load comprehensive context about the user and vault before beginning work
---

# Context Loading

Your job is to build comprehensive context about the user before beginning any work. Read thoroughly and follow backlinks.

**Optional domain filter:** the args passed to this skill

Use the `obsidian` CLI (available in PATH) for all vault queries.

## Step 1: Core Context Files

Read all context files:
```bash
obsidian read file="README"                        # Vault overview and structure
obsidian read file="<Company-Context>"             # Company context
obsidian read file="<Project-Context>"             # Project context
obsidian read file="Personal Workflow Context"     # Scheduling, workflow, preferences
```

## Step 2: Explore Directories

List and understand the contents of key folders:
```bash
obsidian files folder="<Company>"
obsidian files folder="<Project>"
```

## Step 3: Follow Backlinks

As you read each file, follow backlinks and discover connections:
```bash
obsidian backlinks file="<note name>"  # Find what links TO a note
obsidian links file="<note name>"      # Find outgoing links FROM a note
obsidian read file="<linked note>"     # Read linked notes
```

Continue following backlinks recursively until you have read all connected documents.

## Step 4: Recent Daily Notes

Read the most recent daily notes (last 5-7 days):
```bash
obsidian daily:read
obsidian read path="Daily Notes/YYYY-MM-DD.md"  # for each past day
```
Understand:
- What the user has been working on
- What they've been thinking about
- Current priorities and blockers
- Recent decisions and shifts

## Step 4b: Recent Weekly Learnings

Find and read the most recent 2-3 weekly learnings:
```bash
obsidian search query="Weekly Learnings"
obsidian read file="<most recent learnings>"
```
These capture how thinking is evolving week to week.

## Step 4c: Vault Structure & Hidden Connections

Explore the vault's structure and surface things that aren't visible from reading individual files:

```bash
obsidian orphans                    # Notes nothing links to (potentially forgotten or neglected)
obsidian deadends                   # Notes with no outgoing links (isolated thinking)
obsidian unresolved                 # Things referenced in [[brackets]] but never created (gaps)
obsidian tags counts sort=count     # Theme distribution across the vault
```

Use this to understand:
- Which areas of thinking are well-connected vs. isolated
- What ideas have been started but not developed (orphans)
- What the user keeps referencing but hasn't formalized (unresolved links)
- Where attention is concentrated vs. sparse (tag distribution)

Include notable findings in the synthesis.

## Step 5: Synthesis

Once you have read everything, provide a brief synthesis:

1. **Current priorities** - What matters most right now
2. **Active projects** - What's in motion
3. **Open questions** - What's unresolved
4. **Recent shifts** - What's changed in thinking or approach

Then say: "Context loaded. What would you like to work on?"

## Notes

- If a specific domain is passed as an argument (e.g., `/context podcast`), prioritize that domain's files but still read the core context
- Pay attention to confidence markers: `[solid]`, `[evolving]`, `[hypothesis]`, `[questioning]`
- The goal is maximum context so the agent can work effectively without asking basic questions
