---
name: map
description: Obsidian vault skill. Generate a topological view of the vault showing clusters, themes, and how ideas relate
---

# Map — Vault Topology & Intellectual Landscape

Analyze the structure and shape of thinking across the entire vault. Show where ideas are concentrated, where the dead zones are, what's central vs. peripheral, and what connections are missing.

**Usage:** `/map`

---

## Step 1: Structural Analysis

Use the Obsidian CLI to get the full picture of vault structure:

```bash
obsidian tags counts sort=count          # Theme distribution
obsidian orphans                          # Notes nothing links to
obsidian deadends                         # Notes with no outgoing links
obsidian unresolved                       # Referenced but never created
```

Get link density for key notes:
```bash
obsidian backlinks file="<Hub Note A>"
obsidian backlinks file="<Hub Note B>"
obsidian links file="<Hub Note A>"
obsidian links file="<Hub Note B>"
```

Count and categorize:
```bash
obsidian files folder="Daily Notes"       # How many daily notes?
obsidian files folder="Essays"            # How many essays?
obsidian files                            # Total vault size
```

## Step 2: Identify Clusters

Trace the major clusters of thinking by following backlink chains from the most connected notes:

```bash
obsidian backlinks file="<highly connected note>"
obsidian links file="<highly connected note>"
```

For each cluster:
- What's the central node?
- How many notes are in the cluster?
- How dense are the internal connections?
- Does this cluster connect to other clusters, or is it isolated?

### Cluster Relationship Narrative
Don't just list clusters. Describe how they relate to each other:
- Which clusters should be connected but aren't? These are the biggest structural gaps.
- Which clusters are bridged by a single note? That note is a critical junction. If it were removed, two areas of thinking would become disconnected.
- Which clusters are appropriately separate? Not everything needs to connect.
- Where are the superclusters (groups of clusters that form a larger meta-theme)?

## Step 3: Find the Gaps

### Missing Connections
Notes that share themes or concepts but aren't linked to each other. Look for:
```bash
obsidian search:context query="<theme from cluster A>"  # Does this appear in cluster B?
```

### Orphaned Value
Review orphaned notes. For each one, apply this decision logic:
- **(a) Genuinely unrelated?** Some notes are appropriately isolated. Skip.
- **(b) Not connected yet?** Contains ideas relevant to current priorities but was never linked. These are the high-value rescues.
- **(c) Contains forgotten insight?** Something written months ago that's surprisingly relevant to what's active now. Flag for attention.
- **(d) Intentionally isolated or accidentally abandoned?** Check the date and context. Recent orphans are likely accidents. Old orphans may be intentional.

### Unresolved Links
Review unresolved `[[links]]`. These are ideas referenced but never developed:
- Which ones are worth creating notes for?
- Which ones represent important thinking that never got its own space?

### Dead Zones
Areas of stated interest or priority that have very few notes or thin thinking. Compare stated priorities in context files against actual note density.

### Tag-to-Priority Ratio
For the top 10 tags by count, cross-reference against stated priorities in context files:

| Tag | Note Count | Stated Priority? | Ratio |
|-----|-----------|-------------------|-------|
| ... | ... | High/Medium/Low/None | ... |

Ratios where a tag has high stated priority but low note count indicate **dead zones**: areas you say matter but aren't actually developing. Ratios where a tag has high note count but low stated priority indicate **attention sinks**: areas absorbing energy without being strategic.

## Step 4: Synthesize

### Vault Overview
- Total notes, daily notes, essays, context files
- Most connected notes (hubs)
- Most isolated notes (orphans worth rescuing)
- Tag distribution (where thinking is concentrated)

### Cluster Map
List each major cluster with:
- **Name**: What this cluster is about
- **Hub note**: The most connected note in this cluster
- **Size**: Approximate number of notes
- **Density**: How interconnected the notes are
- **Health**: Active and growing / Stable / Stagnant / Neglected
- **Connections to other clusters**: Which clusters does this one bridge to?

### The Shape of Your Thinking
A narrative description of what the vault reveals about where attention and intellectual energy are going. What dominates? What's underdeveloped relative to its stated importance?

### Strongest Connections
The most surprising or valuable links between clusters. Things that connect across domains in non-obvious ways.

### Recommended Actions
- Notes to create (from unresolved links)
- Connections to make (orphans to connect, clusters to bridge)
- Areas to develop (dead zones that matter)
- Notes to revisit (orphaned value worth rescuing)

---

## Output Format

**VAULT MAP -- [Date]**

[Overview stats]

[Cluster map with relationship narrative]

[Shape narrative]

[Tag-to-priority analysis]

[Gaps and dead zones]

[Recommended actions]

---

## Output Guidelines
- Be specific: name actual notes, not abstractions
- The map should make the user see their vault differently than before running this command
- Focus on actionable insights, not just statistics
- The most valuable output is connections that should exist but don't
