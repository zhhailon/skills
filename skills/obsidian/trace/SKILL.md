---
name: trace
description: Trace how an idea or concept has evolved across the Obsidian vault over time
---

# Trace — Idea Evolution Over Time

Trace how a specific idea, concept, or belief has evolved across the vault over time. Shows the full arc of thinking development.

**Topic to trace:** the args passed to this skill

Use the `obsidian` CLI (already installed, available in PATH) for all vault queries. Examples:
- `obsidian search query="<text>"`
- `obsidian search:context query="<text>"`
- `obsidian search query="<text>" path="<folder>"`
- `obsidian read file="<name>"` (or `path="<folder>/<file>.md>"`)
- `obsidian backlinks file="<name>"`
- `obsidian links file="<name>"`
- `obsidian tags counts sort=count`

---

## Step 1: Synonym Discovery

Before searching, build a vocabulary map for this topic. Ideas often evolve under different vocabulary.

1. Read one context file that's most likely to touch this topic (a Map of Content, an index, or a top-level essay on the theme).
2. Extract 3-5 related terms, adjacent concepts, and alternative phrasings.
3. Note any jargon, shorthand, or metaphors used for this idea in the vault.

Then search using the full vocabulary:
```bash
obsidian search query="<topic>"
obsidian search:context query="<topic>"
obsidian search query="<synonym 1>"
obsidian search query="<synonym 2>"
obsidian search query="<related concept>"
```

Also search daily notes specifically (if the vault has a Daily Notes folder):
```bash
obsidian search query="<topic>" path="Daily Notes"
obsidian search query="<synonym 1>" path="Daily Notes"
```

And check context files, essays, and any Maps of Content:
```bash
obsidian search query="<topic>" path="Essays"
obsidian read file="<any context file likely to contain this topic>"
```

**Sparse data handling:** If the initial search returns few results, try broader related terms. If a topic has very few explicit mentions, it may appear implicitly. Move to Step 1.5.

## Step 1.5: Implicit Pattern Detection

Some ideas don't have explicit mentions but emerge through patterns across daily notes. Use broader contextual searches:
```bash
obsidian search:context query="<broader theme>"
obsidian tags counts sort=count  # check if related tags reveal hidden mentions
```

Look for:
- Daily notes that discuss the same problem this idea addresses, without naming it
- Emotional reactions to situations that this idea would explain
- Decisions made that reflect this thinking, even if the thinking wasn't articulated

Implicit mentions are often the earliest evidence of an idea forming.

## Step 2: Follow the Graph

For each note that mentions the topic:
```bash
obsidian backlinks file="<note>"  # what else connects to this?
obsidian links file="<note>"      # what does this link to?
```

Follow backlinks 2-3 hops out from the most significant mentions. The goal is to find:
- Notes that influenced this thinking without mentioning the topic directly
- Related concepts that evolved alongside this idea
- People, conversations, or events that triggered shifts

## Step 3: Build the Timeline

Organize findings chronologically. For each significant mention or shift:
- **Date**: When it appeared
- **Context**: What was happening at the time (from daily notes, calendar if helpful)
- **The thinking**: What was believed or proposed at that point
- **Confidence level**: If marked with `[solid]`, `[evolving]`, `[hypothesis]`, `[questioning]`, note it
- **What triggered the shift**: Conversation, experience, reading, or just time

### Temporal Weighting
Recent mentions (past 3 months) suggest active evolution. The idea is alive and changing. Focus the narrative here. Older mentions establish origin but the story is in the active period.

If there's a long gap between mentions (e.g., nothing for 6 months, then a burst), that gap itself is interesting. What happened? Did the idea go dormant, or did it evolve underground?

## Step 4: Identify the Arc

Synthesize the timeline into a narrative:

### First Appearance
When and where this idea first showed up. What form was it in? Was it a question, a hunch, a reaction to something?

### Key Inflection Points
Moments where the thinking shifted meaningfully. What caused each shift?

### Current Position
Where the thinking stands now. What confidence level? What's resolved vs. still open?

### Confidence Marker Evolution
If the topic appears in a context file with a confidence marker, show how that marker changed over time. Was it `[hypothesis]` and now `[solid]`? When did the shift happen? Was there a specific event that triggered the upgrade? Was it earned through experience, or did it drift to `[solid]` without being tested?

### The Evolution Pattern
What kind of evolution was this? Options:
- **Linear deepening**: Same direction, just more refined over time
- **Pivots**: Fundamental changes in direction
- **Convergence**: Separate ideas that merged into one
- **Divergence**: One idea that split into multiple threads
- **Circular**: Keeps coming back to the same question without resolution

### Unresolved Tensions
Contradictions or open questions that remain. Things written at different times that don't agree with each other.

### What's Next
Based on the trajectory, where is this idea likely heading? What would resolve the open tensions?

---

## Output Format

**TRACE: [Topic]**
**First appeared:** [date]
**Time span:** [X weeks/months]
**Mentions found:** [number of notes]
**Velocity:** [Accelerating / Steady / Dormant]

[Timeline with key moments]

[Arc narrative]

[Confidence marker evolution, if applicable]

[Unresolved tensions]

[What's next]

---

## Output Guidelines
- Be specific: cite exact notes and dates
- Show the actual words used at different times so the evolution is visible
- Don't flatten the complexity. If the thinking contradicts itself across time, show that.
- The value is in seeing the shape of your own thinking from the outside. Make that shape visible.
