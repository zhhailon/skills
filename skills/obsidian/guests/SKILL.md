---
name: guests
description: Obsidian vault skill. Derive who you should be talking to on the show by starting from questions the vault is actively asking
---

# Guests — Derive Who You Should Talk to from What You're Already Thinking About

Scan the vault to find the questions, tensions, and obsessions that are most alive right now. Then work outward from those to find the people in the world whose life's work sits inside those questions. The show doesn't need a guest pipeline. It needs a question pipeline. The guests follow from the questions.

**Usage:** `/guests` (full scan) or `/guests [domain or question]` (focused exploration)

---

## Why This Command Exists

The best podcast episodes happen when the host is already living inside the question the guest has spent years on. The worst episodes happen when the host is learning about the guest for the first time through a brief. This command closes that gap by starting from what's alive in the vault and finding who in the world is the best conversation partner for it.

This is not a guest pipeline tool. It is a resonance detector.

---

## What Counts as a Guest Direction

A guest direction is NOT:
- A famous person who would be "good for the show" (that's PR thinking)
- Someone interesting in the abstract (that's a Wikipedia rabbit hole)
- A name from a guest brief that hasn't been investigated (that's the pipeline problem this command solves)
- Someone already booked or recently recorded (check the context file)

A guest direction IS:
- A person whose life's work intersects with a question the vault is actively wrestling with
- Someone who would bring force into the room because the conversation would be about something both people care about deeply
- A person who has lived inside a domain long enough that 3 hours of conversation would produce genuine discovery
- Someone where the vault already contains enough context on the topic that deep preparation would feel like exploration, not homework

The test: If you named this person and the host's reaction is "oh, I've been thinking about that exact thing," it's a real direction. If the reaction is "yeah they seem cool I guess," it's not.

---

## Step 1: Extract the Live Questions

The vault contains hundreds of ideas. Most are dormant. The goal is to find the 5-10 questions that are most alive RIGHT NOW, meaning they appear in recent writing, recur across domains, carry emotional energy, or represent active tensions.

### Recent Daily Notes (Past 30 Days)
```bash
obsidian daily:read
obsidian read path="Daily Notes/YYYY-MM-DD.md"  # read past 21-30 days
```

Extract questions the vault is asking, not necessarily phrased as questions. Look for:
- Things written about with energy, length, or repetition
- Problems returned to across multiple days
- Subjects explored without resolution
- New interests appearing for the first time
- Frustrations that point at deeper questions
- Moments of genuine excitement or curiosity

### Published and In-Progress Writing
```bash
obsidian search query="article"
obsidian search query="essay" path="Daily Notes"
obsidian files folder="Essays"
```

Read recent articles, drafts, and published work. Writing is the strongest signal of what someone is thinking about. The topics chosen for public writing are the topics with the most energy behind them.

### Context Files
Read your active context files, especially any related to your show or creative work:
```bash
obsidian read file="<show context file>"
obsidian read file="<company or project context file>"
```

Extract:
- Open questions (explicitly listed)
- Items marked `[evolving]` or `[hypothesis]` or `[questioning]`
- Tensions between stated beliefs
- Goals that imply unstated questions

### Meta and Reflective Notes
Read any meta-reflective notes where you think about your work and process in the open:
```bash
obsidian search:context query="thinking about"
obsidian search:context query="wondering"
obsidian search:context query="curious about"
obsidian search:context query="obsessed with"
obsidian search:context query="keeps coming up"
obsidian search:context query="can't stop"
```

### Structural Signals
```bash
obsidian unresolved                 # Referenced but never created notes, these are ideas pulling at you
obsidian tags counts sort=count     # Where attention is concentrated
obsidian orphans                    # Isolated notes that might represent unexplored threads
```

For high-frequency tags and unresolved links, check if they connect to active questions:
```bash
obsidian backlinks file="<high-frequency topic>"
obsidian search:context query="<unresolved link name>"
```

### Question Extraction Rules

1. **Recency matters.** A question from this week beats a question from two months ago, even if the older one has more total mentions.
2. **Energy matters more than frequency.** A single daily note entry written with obvious intensity outweighs a topic mentioned ten times in passing.
3. **Cross-domain questions are strongest.** If the same question appears in personal writing, work context, AND creative output, it's deeply alive.
4. **Unresolved > resolved.** If the vault has already arrived at an answer, the question is dead. Look for active tensions.
5. **Behavioral signals beat stated interests.** What someone writes about unprompted at midnight is more real than what they list as an interest.

### Output from Step 1

Produce a ranked list of 5-10 Live Questions, each stated plainly in one sentence. For each:
- **The question:** [stated plainly]
- **Evidence:** [which notes, dates, and patterns support this being alive]
- **Energy level:** High / Medium / Emerging
- **Domain span:** [which areas of the vault it touches]

---

## Step 2: Map the Question Landscape

For each Live Question, understand its depth and edges in the vault.

### Trace What Already Exists
```bash
obsidian search:context query="<key terms from question>"
obsidian backlinks file="<most relevant note>"
obsidian links file="<most relevant note>"
```

For each question, map:
- **What the vault already knows:** Stated beliefs, experiences, frameworks
- **What the vault doesn't know:** Gaps, uncertainties, the parts of the question that remain unexplored
- **Adjacent territories:** Related topics that border the question but haven't been connected
- **The emotional core:** Why does this question matter to the author? What's at stake personally?

### Check Past Episodes
Search the vault for previous episode notes and your show's context file to see what's already been covered:
```bash
obsidian search query="<your show name> EP"
obsidian read file="<show context file>"   # Notable Past Guests section
```

For each question, check if previous episodes already covered this ground. If so:
- What angle was explored? What wasn't?
- Would a new conversation go deeper, or just repeat?
- Does the previous episode suggest a natural "next guest" in the sequence?

### Check the Current Pipeline
Search for any existing guest pipeline, briefs, or outreach notes:
```bash
obsidian search query="guest"
obsidian search:context query="pipeline"
obsidian search:context query="brief"
```

See if anyone in the existing pipeline actually maps to a Live Question. If they do, flag it. This is how the pipeline stops feeling like homework.

---

## Step 3: Find the People

For each Live Question, identify people in the world whose life's work makes them the ideal conversation partner.

### Three Tiers of Guests

**Tier 1: Deep Practitioners**
People who have spent years, often decades, inside the question. They didn't just write about it. They lived it. Their work IS the answer to the question, even if the answer is "I'm still figuring it out."

**Tier 2: Adjacent Explorers**
People who approach the same question from a completely different domain. They wouldn't describe their work using the same words, but the underlying question is the same. These guests produce the most surprising conversations because the vocabulary collision forces both people to think differently.

**Tier 3: Emerging Voices**
People earlier in their journey who are actively wrestling with the question in public. They may have less "authority" but more raw energy and honesty. These are often the guests where the energy exchange is most equal.

### Guest Identification Method

For each Live Question:

1. **Name the domain the question lives in.**
2. **Name 2-3 adjacent domains.**
3. **For each domain, identify 1-3 specific people** who have spent significant time inside this question.
4. **For each person, assess the energy exchange potential:**
   - Would this person bring their own force into a 3-hour conversation?
   - Is there a genuine two-way exchange, or would the host be carrying the episode?
   - Does this person have a strong digital presence?
   - Is this person accessible?

### Guest Qualification Criteria

Every suggested guest must pass ALL of these:

1. **Question alignment:** Their work directly intersects with a Live Question from the vault. Non-negotiable.
2. **Depth:** They have enough material to sustain 3 hours of deep conversation.
3. **Discovery potential:** There is something genuinely unknown that the conversation could uncover.
4. **Energy:** Based on their public presence, would they bring conversational force?
5. **Digital presence:** Does this person have a body of work that can be researched and explored?

### Disqualification Criteria

Remove any guest who:
- Was already on the show (check past episodes)
- Maps to a question that's resolved in the vault (dead questions don't make good episodes)
- Would require the host to fake interest
- Is suggested purely for audience growth or clout

---

## Step 4: Score and Rank

### Resonance Score

For each guest suggestion, score on five dimensions (1-5 each):

| Dimension | 1 | 3 | 5 |
|-----------|---|---|---|
| **Question Alignment** | Tangential connection | Clear overlap with a Live Question | The person IS the Live Question embodied |
| **Vault Depth** | No existing vault context on their domain | Some related notes | The vault already contains deep thinking on their territory |
| **Energy Exchange** | Host would carry | Balanced but uncertain | The guest would push the host as much as the host pushes them |
| **Discovery Potential** | Everything about them is already public | Some unexplored angles | The conversation could go somewhere neither person has been |
| **Accessibility** | Reclusive, no public presence | Somewhat active, does some interviews | Active online, accessible, has done long-form conversations |

**Total: /25**

### Tiers
- **Book Now (21-25):** The question is burning, the person is ideal, the conversation would be alive. Act on this.
- **Strong Direction (16-20):** Clear alignment, worth pursuing.
- **Worth Tracking (11-15):** Interesting direction but either the question isn't fully alive yet or the person isn't quite right.
- **Not Yet (10 or below):** The connection is too thin. Don't force it.

---

## Step 5: Preparation Paths

For each guest scoring 16+, provide a preparation path. This is not a research brief. It's a curiosity map.

### For Each Guest

**Preparation Path: [Guest Name]**

**The question you'd be exploring:** [State it plainly]

**What the vault already contains:** [Existing notes, thinking, experiences related to this question]

**What to investigate before booking:**
- [Specific work to consume: book, film, talk, album, project]
- [Specific rabbit hole to go down]
- [A question to sit with while consuming their work]

**The opening move:** [What's the first thing you'd want to pull up on screen when you sit down together?]

**The dangerous question:** [The one question that could make this conversation great — risky, goes beyond the safe public narrative]

**Who they connect to:** [Other guests or potential guests this conversation could lead to]

---

## Step 6: The Meta View

### The Question Map
Visualize how the Live Questions relate to each other. Do they cluster? Is there a meta-question underneath all of them? Name it if it exists.

### The Sequence
If these guests were booked in order, what would the arc of the show look like over the next 5-10 episodes?

### The Gap
What questions is the vault asking that NO guest can answer? Name them.

### Pipeline Reconciliation
Are there people already in the guest pipeline who actually map to Live Questions but weren't recognized as such? Flag these.

---

## Output Format

**GUESTS REPORT**
**Date:** [current date]
**Live Questions found:** [number]
**Guest directions generated:** [number]
**Book Now candidates:** [number]

---

### The Live Questions

[Ranked list of 5-10 questions with evidence and energy levels]

---

### Guest Directions

[Organized by Live Question — for each question: the question stated plainly, then the guests mapped to it, scored and ranked]

---

### Book Now (21-25)

[Full profiles with preparation paths]

---

### Strong Directions (16-20)

[Profiles with preparation paths]

---

### Worth Tracking (11-15)

[Brief profiles, note what would need to change for them to move up]

---

### The Meta View

[Question map, sequence, gap, pipeline reconciliation]

---

## Anti-Patterns

**1. The Rolodex**
Generating a list of impressive names without grounding them in the vault's actual questions. Every name must trace back to a Live Question.

**2. The Brief Repackager**
Taking existing guest briefs and dressing them up with vault language. Direction of discovery is vault-first, always.

**3. The Category Filler**
Suggesting one tech person, one arts person, one culture person to "balance" the roster. The show doesn't need category balance. It needs question alignment.

**4. The Safe Suggestion**
Defaulting to well-known figures who would clearly say yes and do a fine interview. Safe guests produce safe episodes.

**5. The Audience Optimizer**
Suggesting guests based on who would drive views or subscribers. Growth comes from depth, not name recognition.

**6. The Repeat**
Suggesting someone who covers ground a previous episode already covered without identifying new territory.

**7. The Energy Ignorer**
Suggesting brilliant people who are known to be flat, guarded, or promotional in conversation.

**8. The Forced Non-Tech**
Suggesting non-tech guests purely to prove the show can expand, without genuine question alignment.

---

## Show Context

**What makes great episodes:** Guest brings their own force. Both people are genuinely discovering something. Moments of surprise, emotion, real disagreement or real alignment. The host's deep preparation meets the guest's lived experience and something neither expected emerges.

**What makes weak episodes:** Host carries the energy. Conversation stays at the level of the guest's public narrative. No genuine discovery.

**The energy exchange principle:** The single biggest predictor of episode quality is whether the guest brings enough conversational force that the host can play off of them rather than generating all the electricity. Score for this ruthlessly.

---

## Output Guidelines

- Every guest suggestion must trace back to specific vault evidence. No evidence, no suggestion.
- Cite exact notes, dates, and quotes.
- Be ruthlessly honest about energy exchange potential.
- The preparation paths should feel like curiosity maps, not homework assignments.
- Prefer fewer, stronger suggestions. Five genuine "Book Now" candidates are better than twenty "Worth Tracking" names.
- The dangerous question for each guest is mandatory. If you can't identify it, the suggestion isn't developed enough.
