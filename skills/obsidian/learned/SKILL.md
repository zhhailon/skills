---
name: learned
description: Obsidian vault skill. Generate three levels of writing (short post, personal essay, universal essay) from vault thinking on a topic
---

# What I Learned — Post Generator

Generate writing from vault thinking. Takes a topic (from argument or today's daily note), mines the vault for raw material, then produces drafts at three levels: a short personal post, a personal essay, and a universal essay that could change how someone thinks about the topic.

**Topic:** the args passed to this skill (if empty, pulls from today's daily note)

Use the `obsidian` CLI (available in PATH) for all vault queries.

---

## Step 1: Find the Raw Material

**If a topic was provided:** Use that as the subject. Search the vault for related notes, daily entries, and context files that touch on it.

**If no topic provided:** Read today's daily note:
```bash
obsidian daily:read
```
If today's note is sparse, read the past 3 days. Extract:
- Insights or realizations written down
- Problems solved or understood
- Shifts in thinking
- Things that surprised you
- Conversations that changed perspective

Pick the most interesting insight as the topic. If multiple are strong, list them and ask which to use.

---

## Step 2: Pull Supporting Context

Once the topic is identified, read relevant files:
```bash
obsidian read file="<context-file-name>"  # for each relevant context file
obsidian search query="<topic>" path="Essays"
obsidian backlinks file="<topic-note>"    # connected notes
```

Then go deeper for unexpected connections:
```bash
obsidian backlinks file="<each connected note>"   # follow 2-3 hops deep
obsidian search:context query="<related concepts>"
obsidian tags file="<topic note>"
obsidian orphans   # check if forgotten notes relate to this topic
```

Look for:
- How long you've been thinking about this (depth of experience)
- Specific details, anecdotes, or moments that make this personal and concrete
- The non-obvious angle (what would surprise someone who hasn't been living this)
- Connection to something universal (why anyone would care)

### Temporal Velocity Check
How fast is this topic developing in the vault?
- **Accelerating** (more notes in the past 2 weeks than the prior month): Ripe — has momentum and fresh thinking. Ready to publish.
- **Steady** (consistent mentions over time): Well-developed but may need a new angle to feel urgent.
- **Decelerating** (most notes are older, fewer recent mentions): May need more lived experience, or a deliberate provocation to reignite. Flag the risk.

---

## Step 3: Research for the Universal Version

Before writing, go beyond the vault. Search for:
- Scientific research, studies, or data related to the topic
- Frameworks or concepts from other disciplines that illuminate it
- Historical examples, analogies, or stories that make the idea vivid
- Counterintuitive findings that challenge conventional wisdom on the topic
- Anything that would make a reader stop and rethink what they thought they knew

The vault gives lived experience. The research gives ammunition to make it hit harder.

---

## Step 4: Understand What Works

Content performs best when it combines:
- **Personal specificity** with **universal resonance**
- **Strong opinions** with **vivid, concrete details**
- **Vulnerability** with **practical wisdom**

Content that underperforms:
- Thinking-out-loud without a complete thought
- Nice observations with no hook
- Reference-saving posts

The pattern: **specific lived experience + non-obvious framing = content that resonates.**

---

## Step 4.5: Identify the Non-Obvious Angle

Before writing, force this analysis:

- **What would surprise someone?** What part of this topic is counterintuitive or contradicts what most people assume?
- **What do conventional sources get wrong?** Where does the lived experience from the vault diverge from standard advice or accepted wisdom?
- **What's the thing nobody says?** Every topic has an obvious take and an honest take. Find the honest one.
- **Where does the vault evidence contradict itself?** Internal tension often produces the most interesting writing. Don't resolve it prematurely.

The non-obvious angle is what separates content that gets saved and shared from content that gets scrolled past.

---

## Step 5: Generate Three Versions

Output THREE versions:

### Version 1: Short Post

A single, self-contained post. Could go on X, could go anywhere.

- 1-3 short paragraphs. Punchy.
- Opens with the sharpest version of the insight or a surprising statement.
- One concrete detail or specific example that grounds it.
- Ends clean. No call to action, no forced wrap-up.

### Version 2: Personal Essay (300-600 words)

Flowing prose grounded in your specific situation.

- Open with the specific moment or experience that triggered the insight. No throat-clearing.
- Build the learning through concrete examples and personal experience.
- Connect to something larger without forcing it.
- End with a question or an open thread, not a neat conclusion.

### Version 3: Universal Essay (800-1500 words)

The version that could change someone's life. Written for anyone experiencing this problem, not about you specifically.

**Before writing, define the reader:**
- **Who is stuck on this?** Describe the specific person this essay is for.
- **What stage are they at?** Early confusion, middle frustration, or late-stage reckoning?
- **What assumptions do they hold?** What will this essay challenge or reframe?
- **What do they need to hear?** Not what they want to hear. What would actually help them move forward.

Write for this specific person.

**The north star: help the reader progress.** The vault notes are the starting point, not the conclusion. If the research, evidence, or honest thinking supports the vault experience, great. If it challenges or complicates it, follow that instead. The goal is giving the reader exactly what they need to see their situation more clearly and take the next step.

The approach:
- **Use the vault notes as the seed, not the conclusion.** The personal experience reveals a question worth exploring. The answer should come from following the evidence honestly.
- **Write for the reader who is stuck.** Give them language for what's happening to them.
- **Bring in everything that hits.** Research, science, metaphor, vivid examples, counterintuitive framings.
- **Diagnose, then reframe.** Show the reader their own experience with precision so they feel seen. Then offer a reframing that shifts how they understand it.
- **Maintain narrative momentum.** Prose that moves. Each paragraph should create enough tension or curiosity that the reader has to keep going.
- **End with expansion, not closure.** Open a door the reader didn't know was there.

What makes this version different from a blog post:
- It's not advice. It's truth-telling.
- It uses specificity without being personal. Third-person vignettes drawn from vault experience, anonymized and universalized.
- It earns its length. Every paragraph does work. No filler, no repetition.
- It serves the reader's development above all else.

### Rules for all three versions:
- Write in the vault author's voice: direct, curious, slightly intense, grounded in real experience.
- Don't be preachy. Share what you found, not what others should do.
- First person for Versions 1 and 2. The universal version can use second person ("you"), third person, or first person — whatever serves the piece best.
- No headers or formatting in the prose. Just writing.

---

## Step 6: Ask for Direction

After presenting all three drafts, ask:
1. Which version feels closest to what you want to publish?
2. Any details to add, remove, or change?
3. Ready to post, or save to vault as a draft?

If saving as a draft, create a file at `Drafts/What I Learned - [Topic] - [DATE].md` with all three versions.
