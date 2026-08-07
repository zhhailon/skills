---
name: obsidian-ideas
description: Obsidian vault skill. Generate ideas across multiple domains from vault patterns to fuel exploration and break through bottlenecks
---

# Ideas Generation

Generate a comprehensive list of ideas across multiple domains to fuel exploration, break through bottlenecks, and improve life. Surfaces both obvious high-impact opportunities and non-obvious insights from patterns in the vault.

Use the `obsidian` CLI (available in PATH) for all vault queries.

---

## Step 1: Vault Relationship Exploration

Start with structural analysis before reading individual files. This surfaces connections that aren't visible from reading files in isolation.

```bash
obsidian orphans                    # Notes nothing links to (forgotten ideas, neglected projects)
obsidian deadends                   # Notes with no outgoing links (isolated thinking)
obsidian unresolved                 # Things referenced in [[brackets]] but never created
obsidian tags counts sort=count     # Theme distribution across the vault
```

For each context file and key daily note theme, trace connections:
```bash
obsidian backlinks file="<note>"             # What else links to this?
obsidian links file="<note>"                 # What does this link to?
obsidian search:context query="<key theme>"  # Where else does this theme appear?
```

Follow backlink chains 2-3 hops deep from the most active themes. Look for:
- Notes that share connections but aren't linked to each other (hidden relationships)
- Orphaned notes that are surprisingly relevant to current priorities
- Unresolved links that represent ideas worth creating notes for
- Tag clusters revealing where thinking is concentrated vs. sparse
- Deadend notes containing valuable thinking that was never connected to anything

### Cross-Domain Pattern Detection
Look for the same problem, question, or theme appearing across multiple domains simultaneously. These convergences signal breakthrough opportunities.

```bash
obsidian search:context query="<pattern from domain A>"  # does it appear in domain B?
```

---

## Step 2: Deep Context Review

### Daily Notes (Past 30 Days)
```bash
obsidian daily:read
obsidian read path="Daily Notes/YYYY-MM-DD.md"  # for each past day
```
Extract:
- Frustrations and friction points mentioned
- Things that sparked energy or excitement
- Recurring interests or curiosities
- Problems mentioned but not solved
- Wishes ("I wish I could...", "It would be nice if...")
- Things tried and abandoned (why?)
- Questions asked but not answered

**Sparse data handling:** If daily notes are sparse, expand to 45-60 days.

### Context Files
```bash
obsidian read file="<Context File A>"
obsidian read file="<Context File B>"
obsidian read file="<Context File C>"
```
Extract:
- Open questions (explicitly listed)
- Hypotheses marked as untested
- Things marked `[questioning]` or `[evolving]`
- Constraints that might be worth challenging
- Goals without clear paths

### Calendar (Past 2 Weeks + Next 2 Weeks)
Review calendar for:
- Where time is actually going (meeting types, patterns)
- What's crowding out exploration time
- Recurring commitments worth questioning
- Gaps that could be used differently

### Social Media Profile
Review recent posts, threads, and engagement:
- Topics you're publicly thinking about
- Posts that got high engagement (what resonates)
- Posts that underperformed (interesting to you but wrong framing?)
- Threads worth expanding into longer content

### Messages (Past 30 Days)
Review recent messages for patterns:
- Conversations that sparked energy or ideas
- People you keep meaning to follow up with
- Plans discussed but not acted on
- Recurring topics across conversations

### Essays & Published Work
```bash
obsidian files folder="Essays"
obsidian search query="<relevant terms>" path="Essays"
```
Look for:
- Throughlines across written topics
- Gaps in what's been explored
- Old ideas worth revisiting
- Things started but not finished

---

## Step 2.5: Temporal Tracking

Before generating ideas, check if previous /ideas runs exist:
```bash
obsidian search query="ideas generation" path="Daily Notes"
obsidian search query="/ideas" path="Daily Notes"
```

If prior runs found:
- Which ideas got traction? (Appeared in later daily notes, got calendar time, produced output)
- Which were abandoned? (Never mentioned again)
- Which keep recurring? (Persistent interests masquerading as ideas — they need commitment, not another suggestion)

Prevent redundant suggestions. If an idea was generated before and went nowhere, either drop it or reframe: "This was suggested on [date] and didn't get traction. What would need to change for it to happen this time?"

---

## Step 3: Pattern Analysis

Before generating ideas, synthesize patterns:

### What's Working
Things that consistently produce energy, output, or satisfaction.

### What's Frustrating
Recurring friction, complaints, or energy drains.

### What's Missing
Gaps between stated goals and current activities. Things desired but not pursued.

### Recurring Interests
Topics, people, or activities that keep coming up across notes.

### Bottlenecks
Places where progress is blocked, often by the same thing repeatedly.

---

## Step 4: Generate Ideas

For each category, generate 3-5 specific, actionable ideas. Prioritize ideas that are:
- High impact (would meaningfully improve life/work)
- Non-obvious (not the first thing that comes to mind)
- Grounded in actual patterns from the vault (not generic advice)

### Tools to Build
Custom tools, scripts, slash commands, or automations that would solve specific problems identified in the vault.

### Tools to Start Using
Existing products, apps, or services that would address identified needs.

### Systems to Implement
Workflows, processes, or routines that would create structure around recurring challenges.

### Products to Purchase
Physical items, subscriptions, or one-time purchases that would improve daily life.

### Habits to Adopt
Behavioral changes or practices to build.

### Subjects to Investigate
Topics worth going deep on, based on recurring interests or open questions.

### Things to Write & Publish
Essay ideas, threads, or content based on unique perspectives or experiences in the vault.

### Films to Watch
Based on interests, themes in work, or creative fuel needs.

### Conversations to Have
People to reach out to, relationships to deepen.

### Experiments to Run
Low-cost tests of ideas, beliefs, or approaches.

---

## Step 5: Prioritize

### Top 5 High-Impact, Do Now
The five ideas across all categories that would have the biggest positive impact and are actionable this week.

### Top 5 High-Impact, Requires Setup
Ideas that need more preparation but are worth investing in.

### Top 5 Non-Obvious Insights
Ideas that emerged from pattern recognition, not obvious from surface-level thinking.

### The One Thing
If you could only act on one idea from this entire list, which one would create the most positive change? Why?

---

## Step 6: Connect to Exploration

### Tomorrow's Exploration
One specific thing to explore tomorrow.

### This Week's Investigation
A subject or project to go deeper on this week.

### This Month's Experiment
A larger experiment to run over the coming weeks.

---

## Output Guidelines

- Be specific, not generic. Every idea should connect to something actually in the vault or observed in activity.
- Cite sources: "Based on your note from [date] about..."
- Distinguish between obvious-but-important and genuinely non-obvious insights.
- Include rough effort/cost estimates where relevant.
- This should feel like talking to someone who deeply understands your situation, not reading a listicle.
