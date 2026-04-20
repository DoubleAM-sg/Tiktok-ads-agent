---
name: humanizer
description: Strip AI-tell from ad-facing copy before showing it to the user. Apply to captions, hooks, headlines, video scripts, and any brainstorm draft shared in conversation. Scope excludes code, commits, internal analysis, and dev docs.
---

# humanizer

Ad copy for PMAL goes to a skeptical Singaporean audience — typically rejected bank applicants. Anything that smells salesy or AI-generated loses them. Run every ad-facing draft through the rules below before presenting.

## Banned punctuation

- **No em dashes** (`—`). Use period, comma, or parentheses.
- **No en dashes** (`–`) in body copy.
- Avoid semicolons in ads. Break into two sentences.

## Banned vocabulary

Replace with plain alternatives:

delve, underscore, tapestry, navigate (as metaphor), seamless, holistic, robust, leverage, utilize, elevate, empower, unlock, game-changer, revolutionary, cutting-edge, furthermore, moreover, nevertheless, meticulously, crucial, vital, comprehensive, intricate, myriad, plethora, paramount, facilitate.

## Banned patterns

- Rule-of-three lists ("fast, easy, and reliable")
- Symmetric parallel constructions ("not just X but Y", "it's not about X, it's about Y")
- Hedging openers ("it's worth noting", "one thing to keep in mind")
- Filler rhetorical questions ("Ever wondered why...?")
- Promotional clichés ("take to the next level", "unlock the power of")
- Vague intensifiers (truly, really, incredibly, absolutely)

## Voice for PMAL

- Plain, direct, short. Sentence fragments are fine.
- First/second person beats third.
- Specific numbers beat vague claims ("1.88% per month" > "low rates").
- Acknowledge audience reality before pivoting: "Banks are first. But if they reject you..."
- Skeptical rejected-applicant audience — salesy copy fails. Sound like a friend who's been through it, not a sales page.

## Output protocol

1. Write the draft.
2. Scan against banned punctuation, vocabulary, patterns.
3. Rewrite every violation.
4. Present cleaned copy only — no before/after diff unless the user asks.
