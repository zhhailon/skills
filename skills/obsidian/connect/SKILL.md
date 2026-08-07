---
name: obsidian-connect
description: Obsidian vault skill. Find unexpected bridges between two domains, projects, or topics in the vault
---

# Connect — Find Unexpected Bridges Between Domains

Takes two separate projects, topics, or domains and uses the vault's graph to find non-obvious connections between them.

**Domains:** the args passed to this skill

Use the `obsidian` CLI (available in PATH) for all vault queries.

---

## Step 1: Map Each Domain

For each of the two domains provided, build a picture of what exists in the vault:

```bash
obsidian search query="<domain A>"
obsidian search:context query="<domain A>"
obsidian backlinks file="<main note for domain A>"
obsidian links file="<main note for domain A>"
obsidian tags file="<main note for domain A>"
```

Repeat for domain B.

Follow backlinks 2-3 hops from each domain's hub notes. Build a list of all notes, people, concepts, and themes that exist in each domain's neighborhood.

### Depth Asymmetry Handling
If Domain A has significantly more notes than Domain B (e.g., 50 vs. 10), pay extra attention to bridges from the smaller domain. The smaller domain's notes often contain insights the larger domain hasn't considered. The less-explored territory is where the surprises are.

When one domain is thin, go deeper on its backlinks. Follow 3-4 hops instead of 2-3. A sparse domain's connections are more valuable per link.

## Step 2: Find the Overlaps

Compare the two neighborhoods. Look for:

### Shared References
Notes that appear in both domains' backlink chains. These are natural bridges.

### Shared People
People mentioned in both domains. What's their role in each?

### Shared Themes
Concepts, values, or questions that appear in both domains even if the notes aren't linked.
```bash
obsidian search:context query="<theme from domain A>"  # search within domain B's neighborhood
```

### Shared Patterns
Structural similarities: both domains facing the same kind of problem, both evolving in the same direction, both stuck on the same question.

### Shared Tags
```bash
obsidian tags file="<notes in domain A>"
obsidian tags file="<notes in domain B>"
```
Tags that appear in both domains indicate thematic overlap.

## Step 3: Trace the Bridges

For each connection found, trace it deeper:
```bash
obsidian backlinks file="<bridging note>"
obsidian links file="<bridging note>"
```

How deep does the connection go? Is it surface-level (same word used) or structural (same underlying pattern)?

### Path-Finding
For the strongest bridges, trace the shortest path between the two domain hubs through the vault graph. What notes sit in between? These intermediary notes are often the most interesting, because they live at the intersection of two worlds without belonging fully to either.

```bash
obsidian backlinks file="<intermediary note>"
obsidian links file="<intermediary note>"
```

What does that intermediary note contain? Why does it connect these two domains? This is often where the real insight lives.

### Temporal Analysis
Sort bridges by date of creation or last modification. Are the domains converging (recent connections increasing) or diverging (connections mostly old, nothing new)?
- **Converging**: Integration is happening naturally. Push it further.
- **Diverging**: The domains used to share more. What changed? Is the separation intentional or drift?
- **Stable**: Consistent connection over time. This is a deep structural link.

## Step 4: Synthesize

### Connection Map
For each bridge found:

**Bridge [#]: [Title]**
- **In Domain A:** [How this concept/note/person appears]
- **In Domain B:** [How it appears differently]
- **The connection:** [What links them, and why it's interesting]
- **Depth:** Surface / Structural / Foundational
- **Implication:** [What this connection suggests for either domain]

### The Strongest Bridge
The single most interesting connection between these domains. The one that reframes how you think about both.

### Missing Links
Connections that SHOULD exist based on the evidence but haven't been made yet. Suggest specific notes to link or create.

### The Question This Raises
What new question emerges from seeing these two domains connected that wasn't visible when they were separate?

---

## Output Format

**CONNECT: [Domain A] <-> [Domain B]**
**Notes in A's neighborhood:** [number]
**Notes in B's neighborhood:** [number]
**Bridges found:** [number]
**Trend:** [Converging / Diverging / Stable]

[Connection map]

[Strongest bridge]

[Missing links]

[The question]

---

## Output Guidelines
- The value is in non-obvious connections. If the bridge is something you already know, dig deeper.
- Always cite specific notes and dates.
- The best output makes you see both domains differently.
- Don't force connections that aren't there. If two domains genuinely don't connect, say so.
