"""Judgment-class detectors for the writing-standards rule catalog.

The declarative catalog (rules.json) is the authoritative source of truth. Most
rules are flat word/regex matches or template slot-fills that the Phase 2 CLI can
run straight from the JSON. A handful of rules need real sentence-level or
document-level logic that cannot be expressed as a flat list; those live here,
each keyed by the same `heuristic_fn` id that the JSON rule references.

Contract for every detector:
    def fn(text: str) -> list[dict]
Return one dict per finding: {"match": <matched text>, "index": <char offset>}.
An empty list means the text is clean for that rule. No detector calls an LLM,
touches the network, or imports anything outside the standard library.

The HEURISTICS registry at the bottom maps each heuristic_fn id (as referenced
from rules.json) to its callable. validate_catalog.py asserts that every
judgment rule's heuristic_fn exists as a key here.
"""

import re

# --- shared vocab ------------------------------------------------------------

# Canonical LLM-diction vocabulary (from slopless words:llm-vocabulary +
# llm-vocabulary-density, deduped). Density rule fires on clustering, not on any
# single word, so common words like "key" are tolerated below the threshold.
#
# 0.4.0 (MAJOR-7): the ten words that ai-vocab-prohibited already bans outright
# as errors (delve, elevate, leverage, realm, robust, seamless, streamline,
# tapestry, transformative, unlock) were removed from this set. Carrying a word
# in both meant one sentence produced an error and a warning for the same word,
# and a passage could cross the density threshold on three words the writer was
# already being told to delete. Public (no leading underscore) because the test
# suite reads it to assert no word carries two severities across rules.
LLM_VOCAB = {
    "additionally", "align", "aligns", "aligned", "bolster", "bolsters",
    "comprehensive", "crucial", "embark", "emphasize", "enhance",
    "foster", "garner", "highlight", "intricate", "interplay", "landscape",
    "meticulous", "moreover", "pivotal", "showcase",
    "testament", "underscore", "valuable", "vibrant", "vital",
    "holistic",
}
LLM_VOCAB_MIN_HITS = 3

# Irregular past participles that write-good / Vale use to catch passive voice
# where a bare "\w+ed" match would miss the verb.
_IRREGULAR_PARTICIPLES = (
    "written", "given", "taken", "made", "done", "seen", "known", "chosen",
    "broken", "stolen", "spoken", "driven", "eaten", "forgotten", "born",
    "beaten", "held", "sent", "built", "found", "kept", "left", "told",
    "shown", "drawn", "thrown", "hidden",
)

# Minor words that stay lowercase in title case.
_TITLE_MINOR = {
    "a", "an", "the", "and", "but", "or", "nor", "for", "of", "to", "in",
    "on", "at", "by", "with", "as", "is", "vs", "via", "per",
}

_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$", re.MULTILINE)


def _word_iter(text):
    for m in re.finditer(r"[A-Za-z']+", text):
        yield m.group(0), m.start()


# --- density -----------------------------------------------------------------

def llm_vocab_density(text):
    """Flag a document that clusters canonical LLM-diction words.

    Fires only when at least LLM_VOCAB_MIN_HITS vocabulary words appear, so an
    isolated "key" or "align" in otherwise plain prose passes clean. Returns one
    finding per matched word once the threshold is crossed.
    """
    hits = [
        {"match": w, "index": i}
        for w, i in _word_iter(text)
        if w.lower() in LLM_VOCAB
    ]
    if len(hits) >= LLM_VOCAB_MIN_HITS:
        return hits
    return []


# --- negation-reframe antithesis ---------------------------------------------

# Correlative form: "not just X but Y" / "not only X but Y".
_NEG_CORRELATIVE = re.compile(
    r"\bnot\s+(?:just|only|merely|simply)\b[^.!?]*?\bbut\b",
    re.IGNORECASE,
)
# Two-clause reframe: "<subject> is not X. <pronoun> is Y."
# Deliberately requires an explicit "is/are not" head and a following
# pronoun-copula clause, so a specific informative rejection like
# "the bottleneck is disk I/O, not CPU" is NOT flagged.
# 0.3.0 (mining-loop CAND-01, Codex-verified): the uncontracted form was caught
# but every contracted/tense variant slipped through ("It wasn't a failure. It
# was a lesson."). The head now also accepts contracted negatives and the tail
# accepts past-tense and do-support copulas, keeping the same two-clause shape.
_NEG_REFRAME = re.compile(
    r"\b(?:"
    r"(?:it's|this is|that's|it is|they are|we are|we're|is|are)\s+not"
    r"|(?:it|this|that|they|we)?\s*"
    r"(?:isn't|wasn't|aren't|weren't|don't|doesn't|didn't|can't|couldn't|"
    r"won't|wouldn't)"
    r")\b"
    r"[^.!?]*[.!?]\s+"
    r"(?:it|this|that|they|we)\s*(?:is|are|was|were|'s|'re)\b",
    re.IGNORECASE,
)


def negation_reframe(text):
    """Flag the "Not X. It is Y." / "not just X but Y" antithesis AI-tell.

    Keeps the negation that carries specific, informative contrast (RULE-07's
    "disk I/O, not CPU" case) clean; targets the vague persuasive reframe only.

    Offset contract (0.4.0 gate fold): the reframe pattern can start on the
    whitespace in front of the negation, so the reported index is advanced past
    whatever the strip() removed. The engine re-slices every reported match out
    of the raw document by index, so a stripped match with an unstripped index
    would report a string one or more characters to the left of what fired.
    """
    findings = []
    for rx in (_NEG_CORRELATIVE, _NEG_REFRAME):
        for m in rx.finditer(text):
            s = m.group(0)
            lead = len(s) - len(s.lstrip())
            findings.append({"match": s.strip(), "index": m.start() + lead})
    return findings


# --- hidden-actor passive voice ----------------------------------------------

# 0.5.0 NARROWING, forced by measurement. Until now this matched ANY to-be verb
# plus a participle: "is built", "is done", "are handled". Measured against 530
# rows of real shipped prose that shape fired 103 times on prose judged fine, so
# the rule scored zero true positives and 103 false positives on real writing. The
# reason is grammatical rather than accidental: "the report is written nightly"
# describes a system's steady state, where the actor is the system and naming it
# adds nothing. What the rule was actually written to catch is the promise made
# to a reader about a future action nobody owns, "your request will be
# reviewed" - there a real person will do a real thing and the sentence hides
# who. So the pattern now requires a modal or future auxiliary in front of
# "be": will/would/can/could/shall/should/may/might/must/to. On the same 530
# rows that leaves 3 firings instead of 103.
#
# The reported match stays the "be reviewed" core (the modal is context, not the
# defect), so the catalog's expected_output and every offset contract are
# unchanged.
_PASSIVE_RE = re.compile(
    r"\b(?:will|would|can|could|shall|should|may|might|must|to)\s+"
    r"(?P<core>be\s+"
    r"(?P<part>\w+ed|" + "|".join(_IRREGULAR_PARTICIPLES) + r"))\b"
    r"(?!\s+by\b)",
    re.IGNORECASE,
)
# "indeed" trips the \w+ed arm; exclude it.
_PASSIVE_FALSE = re.compile(r"\b(?:am|are|were|being|is|been|was|be)\s+indeed\b",
                            re.IGNORECASE)

# Words that end in -ed but are NOT passive participles after a to-be verb.
# Phase 3 tuning: the bare `\w+ed` arm grabbed predicate adjectives ("is red",
# "was excited") and short non-verbs ("bed", "fed"), the noisiest false-positive
# class flagged in Phases 1-2. Two guards below kill both: this curated set of
# common predicate adjectives / non-participles, plus a minimum-stem check that
# drops 3-letter -ed words (red/bed/fed/wed/led/ted) generically.
_PASSIVE_ADJ_STOP = {
    # short non-participle -ed words the \w+ed arm wrongly grabs
    "red", "bed", "fed", "wed", "ted", "bred", "sled", "shed",
    # common predicate adjectives: a STATE, not a hidden-actor action
    "excited", "tired", "interested", "pleased", "bored", "worried",
    "scared", "confused", "married", "relaxed", "surprised", "concerned",
    "involved", "located", "based", "aged", "sacred", "naked", "detailed",
    "delighted", "frustrated", "satisfied", "committed", "dedicated",
    "experienced", "advanced", "limited", "related", "complicated",
    "supposed", "used", "needed", "crowded", "gifted", "talented",
    "skilled", "aligned", "focused", "engaged", "prepared", "qualified",
}


def _is_real_participle(part):
    """True if `part` should count as a passive past participle.

    Rejects the curated predicate-adjective / non-participle set and any -ed word
    with a stem shorter than two letters (red, bed, fed, wed, led, ted). The
    irregular participles (written, sent, built...) never end in -ed, so they
    skip the stem check and only face the stop set.
    """
    p = part.lower()
    if p in _PASSIVE_ADJ_STOP:
        return False
    if p.endswith("ed") and len(p) - 2 < 2:
        return False
    return True


def hidden_actor_passive(text):
    """Flag a promised future action whose actor is hidden: modal + be + participle.

    "The request will be reviewed" hides the reviewer; "the support team will
    review the request" names the actor and passes clean. A trailing "by ..."
    exempts the match (the actor is stated). Phase 3 dropped predicate
    adjectives ("is red", "was excited") and short -ed non-verbs; 0.5.0 dropped
    the whole bare to-be arm ("is built", "are handled") after it scored 0
    true positives against 103 false positives on real shipped prose. See the
    comment on _PASSIVE_RE for the measurement and the reasoning.
    """
    findings = []
    for m in _PASSIVE_RE.finditer(text):
        if _PASSIVE_FALSE.match(text, m.start("core")):
            continue
        if not _is_real_participle(m.group("part")):
            continue
        # Same index/strip contract as negation_reframe: keep the reported index
        # pointing at the first character of the reported match, defensively,
        # even though this pattern currently cannot start on whitespace.
        s = m.group("core")
        lead = len(s) - len(s.lstrip())
        findings.append({"match": s.strip(), "index": m.start("core") + lead})
    return findings


# --- weasel attribution with citation suppression ----------------------------

_WEASEL_ATTRIBUTION_RE = re.compile(
    r"\b(?:experts agree|studies show|research suggests|doctors say|"
    r"it is widely accepted|a growing body of evidence|industry leaders agree)\b",
    re.IGNORECASE,
)
# Explicit citation evidence (0.3.0, Codex-tightened CAND-20): a four-digit
# year, "et al.", a URL, or "according to <Named Source>". Deliberately narrow;
# a bare proper noun or number in the sentence is NOT evidence, or "Studies
# show the 3 top vendors" would wrongly pass.
_CITATION_EVIDENCE_RE = re.compile(
    r"(?:\b(?:19|20)\d\d\b|\bet al\.?|https?://|\baccording to\s+[A-Z])"
)
_SENTENCE_SPLIT_RE = re.compile(r"[.!?]\s+|\n{2,}")


def _sentence_bounds(text, index):
    """Character range of the sentence containing `index`."""
    start = 0
    for m in _SENTENCE_SPLIT_RE.finditer(text):
        if m.end() <= index:
            start = m.end()
        else:
            return start, m.start()
    return start, len(text)


def weasel_attribution(text):
    """Flag a vague appeal to unnamed authority, unless the same sentence
    carries explicit citation evidence (year, et al., URL, or a named
    'according to' source)."""
    findings = []
    for m in _WEASEL_ATTRIBUTION_RE.finditer(text):
        s, e = _sentence_bounds(text, m.start())
        if _CITATION_EVIDENCE_RE.search(text[s:e]):
            continue
        findings.append({"match": m.group(0), "index": m.start()})
    return findings


# --- doubled word (lexical illusion) -----------------------------------------

# Accidental repetition, including across a line break: "the the", "on on".
# Whitespace-only separator means a period/comma between the words breaks the
# match, so "to Paris. Paris loved it" and "very, very" stay clean by shape.
_DOUBLED_WORD_RE = re.compile(r"\b([A-Za-z]{2,})[ \t\r\n]+\1\b", re.IGNORECASE)
# Grammatically legitimate doublings (proselint's own exception set).
_DOUBLED_OK = {"that", "had"}


def doubled_word(text):
    """Flag an accidentally repeated word ("the the"), the classic typo that
    survives rereading because the repeat crosses a line break.

    "that that" and "had had" are grammatical and exempt; a sentence boundary
    between the repeats keeps them clean. Inline code (`retry retry`) is command
    text, not prose, and is already blanked by the CLI's shared masking pre-pass
    before this detector ever sees it (0.4.0 retired the private mask that used
    to live here).
    """
    findings = []
    for m in _DOUBLED_WORD_RE.finditer(text):
        if m.group(1).lower() in _DOUBLED_OK:
            continue
        findings.append({"match": m.group(0), "index": m.start()})
    return findings


# --- heading case (genre-scoped resolution of the corpus conflict) -----------

def _heading_words(title):
    return re.findall(r"[A-Za-z][A-Za-z']*", title)


def heading_title_case(text):
    """Agent-facing genre: headings should be title/short case.

    Flags a heading that reads as sentence case (first or a major word left
    lowercase). "Build the Rule Catalog" passes; "build the rule catalog" and
    "this is a lowercase heading" are flagged.
    """
    findings = []
    for m in _HEADING_RE.finditer(text):
        title = m.group(2)
        words = _heading_words(title)
        if not words:
            continue
        bad = False
        for idx, w in enumerate(words):
            is_first_or_last = idx == 0 or idx == len(words) - 1
            minor = w.lower() in _TITLE_MINOR
            if w[0].islower() and (is_first_or_last or not minor):
                bad = True
                break
        if bad:
            findings.append({"match": title, "index": m.start(2)})
    return findings


def heading_sentence_case(text):
    """Doc genres: headings should be sentence case, not Title Case.

    Flags a heading that capitalizes multiple words past the first (the slopless
    sentence-case tell). "Build the rule catalog" passes; "This Is A Title Case
    Heading" is flagged. Proper-noun-heavy headings may over-trigger; Phase 3
    tunes the threshold.
    """
    findings = []
    for m in _HEADING_RE.finditer(text):
        title = m.group(2)
        words = _heading_words(title)
        if len(words) < 2:
            continue
        capped_after_first = sum(1 for w in words[1:] if w[0].isupper())
        if capped_after_first >= 2:
            findings.append({"match": title, "index": m.start(2)})
    return findings


# --- registry ----------------------------------------------------------------
# Maps each rules.json heuristic_fn id to its callable. Keep keys in sync with
# the judgment rules in rules.json; validate_catalog.py enforces the link.

HEURISTICS = {
    "llm_vocab_density": llm_vocab_density,
    "negation_reframe": negation_reframe,
    "doubled_word": doubled_word,
    "weasel_attribution": weasel_attribution,
    "hidden_actor_passive": hidden_actor_passive,
    "heading_title_case": heading_title_case,
    "heading_sentence_case": heading_sentence_case,
}
