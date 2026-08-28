---
title: AEO / GEO Copywriting Reference
date: 2026-07-10
purpose: Operational playbook loaded by the aeo-copywriter agent at runtime. Distilled from the verified source sweep at active/personal/working-files/research/aeo-geo-ai-search-research-2026-07-10.md.
---

# AEO / GEO Copywriting Reference

Primary sources (shorthand used below): [GEO] = arxiv 2311.09735 (KDD 2024, Aggarwal et al.); [SR] = Semrush study series; [Profound] = Profound AEO + citation pattern guides; [Conductor] = Conductor Academy guide; [a16z] = a16z GEO piece (Zach Cohen, 2025).

## Priority Order (highest lift first)

1. Expert quotes with attribution (+41% Position-Adjusted Word Count in some domains). [GEO]
2. Cited statistics with sources, chosen and framed for human impression, not just accuracy (+31% visibility). See Stat Selection and Framing. [GEO]
3. Outbound citations to authoritative sources (+28%). [GEO]
4. Fluency and clean prose structure (+28%, no new facts required). [GEO]
5. Question-based headings and direct answer openers. [Profound] [SR] [Conductor]
6. E-E-A-T signals: named author, date, credentials. [Conductor] [SR]
7. Schema markup. [SR Tech]
8. Topical authority cluster (10+ interlinked pages). [SR]

## Structure Rules

- Open every piece with a 30-60 word direct answer that is self-contained and extractable. AI engines lift this verbatim.
- H2/H3 headings should mirror natural-language questions (e.g., "How does X work?" not "Overview of X").
- Every section should answer a question in isolation; assume the model will quote it without surrounding context.
- Use bullets and short labeled phrases to improve model parseability. [GEO] [SR]
- Do NOT keyword-stuff: tested 8-10% below baseline compared with fluent prose. [GEO]

## Evidence and Authority (E-E-A-T)

- Named author with credentials is a prerequisite filter, not a nice-to-have. [Conductor]
- Dated content matters: within ~30 days receives substantially more citations on fast-moving topics. [multiple practitioners]
- Unsourced numeric claims are an exclusion trigger. Every number needs a source attribution inline.
- Original data, internal studies, or comprehensive first-party guides earn the highest citation rates. [a16z] [SR]
- External mentions and brand search volume (correlation 0.334) predict LLM citation better than backlinks. [SR]
- Backlinks show weak/neutral correlation with AI visibility; this diverges sharply from classical SEO. [SR]

## What NOT to Do

- No keyword stuffing (documented penalty). [GEO]
- No anonymous authorship or missing dates.
- No unsourced statistics or floating percentages; fabricating them defeats E-E-A-T entirely.
- No stats that land flat: trivial dollar amounts, small raw counts, or internal effort metrics the reader does not track. Reframe or cut them (see Stat Selection and Framing).
- No generic category words where a specific name or number can stand. Vague claims get skipped.
- No reliance on organic rank alone: ~90% of ChatGPT-cited pages rank position 21+ in Google. [SR Comp]

## Schema Recommendations

- FAQPage: highest signal for question-format content.
- Article + datePublished + author: baseline for all editorial content.
- HowTo: step-by-step instructional pieces.
- Organization + sameAs: brand entity disambiguation.
- URL slugs: 17-40 characters; peak citation volume at 21-25 chars. [SR Tech]
- Add LLMs.txt permitting AI crawler access; becoming a baseline expectation. [SR Guide]

## Platform Differences

- ChatGPT: favors encyclopedic, factual, Wikipedia-style coverage. Prioritize depth and precision.
- Perplexity: favors Reddit and YouTube; community-voice and practical angle gets cited more.
- Google AI Overviews: balances authority with UGC; ~38% of citations from top-5 traditional domains. [Profound Cit]
- Topical authority performs best across all three platforms. No single format wins everywhere. [a16z]

## Topical Authority

- Domains with 10+ interlinked pages on a topic earn citations 2-3x more than single hero pages. [SR]
- Cluster strategy: a hub page plus supporting subtopic pages, internally linked, outperforms isolated articles.
- Brand search volume is the strongest single predictor of LLM citation (correlation 0.334). Build the brand, not just the page. [SR]

## Claim Integrity

- Every statistic in the copy must trace to a named source. If a client's claim has no source, note it and prompt them for one before publishing.
- Expert quotes must be real, attributed, and verifiable. Do not synthesize a quote or approximate one.
- If a strong stat or quote does not exist, use vivid specifics (case detail, named example, first-party data) rather than a generic claim.

## Stat Selection and Framing

A number's job is the impression it leaves on the reader, not its precision. Before using any stat, convert it to the reaction a real buyer would have and ask: does this make them think "impressive," or "so what?" Verified and citable is necessary but not sufficient. A true number that lands flat weakens the copy and should be reframed or cut.

Lead with stats that land:

- Magnitude that sounds big on its own: total reach, audience, or volume ("reached 5,539 prospects," "serving 27,000 agents," "15,900 emails sent").
- Multiples and dramatic deltas: doublings, halvings, "cut cost per click by a third," "from zero to a number-two ranking." A change reads stronger than a static level.
- Benchmark-beating comparisons: pair the number with the norm so the reader knows it is good ("a 63% open rate against the ~39% B2B average"). A bare "63% open rate" leaves them guessing whether that is good.
- Outcomes the buyer feels: leads, calls, jobs booked, revenue, pipeline, deals, cost per lead when meaningful. These outrank activity metrics.
- Speed when it is fast: "live in eight weeks from almost nothing."
- Position: "#1/#2 for [the term they would actually search]."

Cut or reframe stats that fall flat:

- Trivial absolute dollar amounts. "Saved $397 a year" makes an owner shrug. Cut it, or express it as a share ("cut their tooling cost by a third") if the percentage is stronger.
- Raw counts that sound small out of context ("twelve pages indexed," "nine automations"). Give them stakes ("from a single indexed page to a fully indexed site ranking number two") or drop the count. A count earns a spot only when the number itself signals scale ("201 spec sheets").
- Internal or technical effort metrics the buyer does not track: "an 841-line SEO package," "deliverability score 70 to 82," "authentication score." These describe your effort, not their outcome. Translate to the result or cut.
- Bare tiny percentages with no delta or benchmark ("a 2.47% click-through rate" on its own).
- Needless precision. "$13.55 to $9.22" reads to a human as "cut cost per click by about a third." Lead with the third; keep the exact figures as support.

How to reframe without lying:

- Lead with the outcome, support with the specific: "more than doubled click-through (2.47% to 5.21%)."
- Convert between absolute and relative for whichever is more impressive, and keep it true.
- Always give a number its yardstick: a benchmark, a baseline, or a goal, so the reader can tell it is good.
- Never invent or inflate to make a stat land (see Claim Integrity). If the honest number is weak, use a vivid specific instead of a generic claim.

The test: read the sentence aloud as if telling a skeptical business owner. If they would say "so what?" or "is that even good?", fix the framing before it ships. Keep the exact figure in the copy for AI-engine citation and frame it for human impact; the two are not in conflict. Give the number and its meaning.

## Source of Each Claim

- Effect sizes (+31%, +41%, +28%, -8-10%): GEO paper, arxiv 2311.09735, KDD 2024, Table 3 / findings section.
- Platform citation patterns (ChatGPT/Perplexity/Google split): Profound citation patterns study, Aug 2024-Jun 2025.
- URL slug range (17-40 chars): Semrush technical-seo-impact-on-ai-search study, 230,000+ prompts.
- Brand volume correlation (0.334), backlink weakness, 10+ pages cluster finding: same Semrush study.
- ~90% of ChatGPT citations rank 21+: Semrush AI mode comparison study.
- E-E-A-T exclusion trigger (missing author/date/sourced numbers): Conductor Academy guide, updated 2026-05-05.
- Direct answer openers, question headings, self-contained passages: Profound AEO guide (Nick Lafferty, 2026-01-29) + Conductor.
- LLMs.txt baseline: Semrush 2026 guide (2026-03-17).
- Original research earning highest citation rates: a16z GEO piece (2025-05-28).
