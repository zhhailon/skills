---
name: obsidian-graduate
description: Obsidian vault skill. Extract ideas buried in daily notes and promote them into standalone permanent notes
---

# Graduate — Daily Note Idea Extractor

## Purpose
This tool scans recent daily notes to surface ideas worth developing into standalone notes, enabling them to create connections through backlinks.

---

## Step 1: Scan Recent Daily Notes

Use the Obsidian CLI to read the past 14 days:
```bash
obsidian daily:read
obsidian read file="YYYY-MM-DD"
```

Extract candidates by identifying:

### Explicit signals
- `#idea` and `#expand` tags
- Language indicating development intent ("should write about," "worth investigating")
- Named concepts and capitalized terms
- Unresolved `[[links]]` representing genuine ideas

### Implicit signals
- High-energy passages with strong language or length
- Original claims or frameworks (positions, not just events)
- Themes appearing 3+ times across days
- Recurring unanswered questions

### Exclude
- Tasks and to-dos
- Meeting logistics
- Unfocused venting
- Concepts already with standalone notes

---

## Step 2: Cross-reference with Existing Vault

Check each candidate:
```bash
obsidian search query="<concept>"
obsidian backlinks file="<concept>"
```

Categorize as:
- **New concept** – Best for graduation
- **Underdeveloped** – Candidate for enrichment
- **Already covered** – Skip unless adding unique value
- **Recurring unresolved** – High priority

---

## Step 3: Present Candidates

Display in priority-ordered table with: idea/concept, source, frequency, status, recommendation.

Include 1-2 sentence summaries, exact quotes (max 125 characters), and vault connections.

---

## Step 4: Graduate Selected Ideas

**For new standalone notes:**
1. Create in vault root
2. Write mini-essay capturing core claim, context, and connections
3. Use original voice and energy
4. Add bidirectional backlinks
5. Update source daily notes with `[[links]]`

**For existing notes:**
1. Read current note
2. Add dated content from daily notes
3. Update backlinks
4. Refresh source daily note links

**For MOCs:**
1. Read relevant MOC
2. Add idea in appropriate section
3. Create bidirectional backlinks

---

## Step 5: Summary

Report:
- Graduated notes created/enriched
- Skipped ideas remaining in queue
- Vault health metrics: total ideas found, graduation rate, tagged vs. untagged discovery gap, recurring ungraduated themes

---

## Guidelines

- Keep notes brief (3-8 paragraphs)
- Preserve original thinking voice
- Present candidates when uncertain
- Target 5-10 minutes per run
- Always request permission before file modifications
