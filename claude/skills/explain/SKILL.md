---
name: explain
description: Re-express the last answer (or a term you name) in plain English, expanding every piece of jargon so a non-technical reader can act on it.
disable-model-invocation: true
---

# /explain - Say it again in plain English

When an answer had jargon in it, type `/explain` and get it back in ordinary words.

Which target:
- If an argument was given (a term, a passage, or "the X part"), explain THAT specifically.
- If no argument, take the most recent substantive answer and rewrite it plainly.

Do this to the target:
- Lead with one sentence saying what this is about. The reader can stop there and
  have the gist.
- Expand every acronym, technical term, file name, and any shorthand used earlier
  in the session. Say what a thing DOES in ordinary words, not just its name. A name
  is a pointer, not an explanation.
- Expand a niche term once, then use plain words. Never swap one piece of jargon for
  another.
- Spell out each consequence: what happens, to whom, after which action, and why a
  trap looks like the right move.
- Keep the fix attached to each problem, so the reader knows what to do about it.
- Describe behaviour, not identifiers. Not "FOO does two jobs" and stop; say what the
  two jobs are in plain words.

Keep every number, condition, and caveat from the original. Plain English is not
vague or dumbed-down. Do not pad and do not condescend. Aim for about the same length
as the original (modestly longer at most); if it triples, you are over-explaining
basics, so cut those, not the substance.

If the target is ambiguous (several recent answers, or an unclear argument), ask
which one before rewriting.
