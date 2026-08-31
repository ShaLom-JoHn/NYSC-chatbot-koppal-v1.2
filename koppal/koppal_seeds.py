"""koppal_seeds.py -- Phase 3 step 1 of the answer resolution order: the per-question answer.

`_chat_body` resolves an answer in four steps: per-question answer, branch answer, intent
chat_answer, prose answer. This module is step 1. It holds no NYSC content of its own: the answers
live in data/question_answers.csv, keyed on seed_id, and the questions that reach them live in the
training source. Delete the sidecar and every lookup returns None, so the engine falls back to
chat_answer exactly as it did before Phase 3 existed.

How a message reaches an answer. The classifier picks the intent, then within that intent only,
the message is compared against every seed's member questions plus its canonical question label.
Nearest neighbour on 0.7 word-ngram cosine plus 0.3 char-ngram cosine, the same recipe used
elsewhere in this project, fitted per intent so words that are ubiquitous inside one intent stop
carrying weight.

MATCH_FLOOR is deliberately strict, and stricter than nlu.SUGGEST_FLOOR, because the two failures
are not comparable. A bad suggestion costs the user a glance, since chips are offered and they
choose. A bad seed match answers a question they did not ask, silently, with nothing on screen to
correct it. Falling through costs nothing at all, because the intent's chat_answer is what they
would have got anyway.

0.45 is measured, not picked. `_seed_matcher_eval.py` runs the match leave-one-out over the
pilot intent, hiding each question and matching it against everything else:

    floor   matched      right seed when matched   wrong seed served
     0.25    88 / 103          80.7%                   17
     0.35    68 / 103          91.2%                    6
     0.40    54 / 103          92.6%                    4
     0.45    42 / 103          97.6%                    1
     0.50    36 / 103          97.2%                    1

Coverage past 0.45 stops buying accuracy, and below it the silent-wrong-answer count climbs fast.
Read the coverage column as optimistic: it is leave-one-out over the questions the seeds were built
from, so real phrasings will match lower.

Including each seed's canonical label in the index is a requirement, not a nicety. 21 of the
pilot's 44 groups hold a single question, so leave-one-out leaves them with nothing to match
against, and without the labels those groups would be structurally unreachable -- the
`ppa_course_matching` failure, where correct content existed and nothing could route to it.
Measured: 18 of 19 singletons in the earlier run landed on their own seed via the label.
"""
import csv

SIDECAR_PATH = "data/question_answers.csv"
SOURCE_PATH = "nysc_question_source-1.csv"

MATCH_FLOOR = 0.45
# A near-exact match answers WITHOUT the classifier having to commit to an intent. The bar is
# higher than MATCH_FLOOR because there is less corroborating evidence: MATCH_FLOOR runs after
# the classifier has already agreed on the intent, this runs instead of it. Measured leave-one-out
# by `_seed_matcher_eval.py`, which is the pessimistic case since a question in the index is
# hidden from itself:
#
#     floor   matched      right seed when matched   wrong seed served
#      0.45    46 / 101          97.8%                   1
#      0.50    37 / 101          97.3%                   1
#      0.60    26 / 101         100.0%                   0
#      0.70    13 / 101         100.0%                   0
#
# 0.60 is where wrong answers stop entirely, and the coverage it gives up is coverage the normal
# post-classification path still handles. In production a question already in the corpus scores
# 1.0 against itself, so this fires on the cases where it is most certainly right.
#
# RE-MEASURED once a second intent had seeds, and the floor alone no longer held: 36 fired and 2 were
# cross-intent wrong, the worst at 0.80. The fix is the uniqueness gate in `lookup_direct`, not a
# higher floor, and this is the counterintuitive part: **raising DIRECT_FLOOR makes it worse.** The
# gate can only suppress a bad match when the RIGHT intent also clears the floor, so at 0.65 and
# above the true intent drops out, the gate goes inert, and the wrong answer fires again. Measured
# across both seeded intents by `_direct_floor_eval.py`:
#
#     floor   ungated fires / wrong      gated fires / wrong      held back
#      0.50        55 / 5                    49 / 3                   6
#      0.55        44 / 3                    40 / 1                   4
#      0.60        36 / 2                    32 / 0                   4
#      0.65        27 / 2                    27 / 2                   0
#      0.70        20 / 1                    20 / 1                   0
#
# So 0.60 and the gate are a pair, and neither number should be moved without re-running that sweep.
DIRECT_FLOOR = 0.60

_index = {}      # intent -> {"texts", "seeds", "word", "char", "Iw", "Ic"}
_answers = {}    # (intent, seed_id) -> answer
_ready = False


def load(sidecar_path: str = SIDECAR_PATH, source_path: str = SOURCE_PATH):
    """Build the per-intent match index. Safe to call when the sidecar is absent: every
    lookup then returns None and the engine falls back to chat_answer.

    Two kinds of sidecar row. `kind=answer` is the normal one. `kind=block` carries NO answer and
    exists only to be matched: it puts a question we cannot answer into the index so that question
    matches itself at 1.00, beats its neighbours, and resolves to nothing, which sends the reply down
    the ordinary lead-plus-branch path. That works without a special case downstream, because
    `lookup` ends on `_answers.get(...)` and a blocker is deliberately absent from `_answers`.

    `kind` is read by name and defaults to `answer` when the column is missing, so an older sidecar
    loads unchanged. An `answer` row with an empty answer is still DROPPED rather than treated as a
    blocker: a blank where content belongs is the shifted-column corruption, not an instruction.
    """
    global _ready, _index, _answers
    _index, _answers, _ready = {}, {}, False

    try:
        with open(sidecar_path, encoding="utf-8-sig", newline="") as f:
            raw = [r for r in csv.DictReader(f) if (r.get("seed_id") or "").strip()]
    except FileNotFoundError:
        return False

    rows, blocks, bad = [], [], []
    for r in raw:
        kind = ((r.get("kind") or "answer").strip().lower()) or "answer"
        answer = (r.get("answer") or "").strip()
        if kind == "block":
            blocks.append(r)
        elif kind == "answer" and answer:
            rows.append(r)
        elif kind == "answer":
            continue          # empty answer, dropped as before
        else:
            bad.append(kind)
    if bad:
        raise ValueError("unknown sidecar kind %r, expected answer or block" % sorted(set(bad))[0])
    if not rows and not blocks:
        return False

    from sklearn.feature_extraction.text import TfidfVectorizer

    csv.field_size_limit(10_000_000)
    with open(source_path, encoding="utf-8-sig", newline="") as f:
        src = list(csv.DictReader(f))

    # every question that belongs to a seed we index, answered or blocked
    indexed = rows + blocks
    wanted = {(r["intent"].strip(), r["seed_id"].strip()) for r in indexed}
    members = {}
    for row in src:
        key = ((row.get("intent") or "").strip(), (row.get("seed_id") or "").strip())
        if key in wanted:
            q = (row.get("question") or "").strip()
            if q:
                members.setdefault(key, []).append(q)

    for r in rows:
        intent, seed = r["intent"].strip(), r["seed_id"].strip()
        _answers[(intent, seed)] = (r["answer"].strip(),
                                    (r.get("terminal") or "").strip().lower() == "yes")

    by_intent = {}
    for (intent, seed) in wanted:
        texts = list(members.get((intent, seed), []))
        label = next((r["question"].strip() for r in indexed
                      if r["intent"].strip() == intent and r["seed_id"].strip() == seed), "")
        if label:
            texts.append(label)          # what makes a single-question seed reachable
        for t in texts:
            by_intent.setdefault(intent, {"texts": [], "seeds": []})
            by_intent[intent]["texts"].append(t)
            by_intent[intent]["seeds"].append(seed)

    for intent, d in by_intent.items():
        word = TfidfVectorizer(ngram_range=(1, 2), min_df=1).fit(d["texts"])
        char = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1).fit(d["texts"])
        _index[intent] = {
            "seeds": d["seeds"],
            "word": word, "char": char,
            "Iw": word.transform(d["texts"]), "Ic": char.transform(d["texts"]),
        }

    _ready = True
    return True


def _best(message: str, intent: str):
    """(seed_id, similarity) for the closest seed inside one intent, or None."""
    from sklearn.metrics.pairwise import cosine_similarity

    d = _index[intent]
    sim = (0.7 * cosine_similarity(d["word"].transform([message]), d["Iw"])
           + 0.3 * cosine_similarity(d["char"].transform([message]), d["Ic"]))[0]
    i = int(sim.argmax())
    return d["seeds"][i], float(sim[i])


def lookup(message: str, intent: str):
    """(answer, terminal) for this message inside this intent, or None.

    None is the normal outcome and never an error: it means no seed was close enough, so the
    caller uses the intent's chat_answer, which is the pre-Phase-3 behaviour.

    `terminal` is True for an answer that should end the turn. "No, that is not a ground" must not
    be followed by "which ground applies, and what stage are you at", so the caller suppresses the
    Conditional follow-up. Everything else keeps its follow-up, because the follow-up is what holds
    the pending slot: without it the ground the user just told us is forgotten by the next turn.

    A BLOCKER returns None here even when it wins above the floor, because it is not in `_answers`.
    That is the whole mechanism: the question reaches the lead on purpose instead of being served a
    neighbour's answer by accident. Nothing downstream needs to know blockers exist.
    """
    if not _ready or not message or intent not in _index:
        return None
    seed, score = _best(message, intent)
    if score < MATCH_FLOOR:
        return None
    return _answers.get((intent, seed))


def probe(message: str, intent: str):
    """(outcome, seed_id, score) with outcome "answer", "block" or "none". For the check scripts.

    `lookup` cannot distinguish "nothing was close" from "the closest thing is a question we know we
    cannot answer", and those are different facts when auditing. Both return None at runtime, which
    is correct, but a check that prints "falls through to the lead" should be able to say which.
    """
    if not _ready or not message or intent not in _index:
        return ("none", "", 0.0)
    seed, score = _best(message, intent)
    if score < MATCH_FLOOR:
        return ("none", seed, score)
    return ("answer" if (intent, seed) in _answers else "block", seed, score)


def lookup_direct(message: str):
    """(intent, answer, terminal) when the message is essentially a KNOWN question, else None.

    Searches every intent that has seeds and requires DIRECT_FLOOR, so it can answer before the
    classifier is consulted at all. That is the point: a question the classifier is not confident
    enough to route still gets answered outright instead of being offered back as a guess, which
    is what "the suggestion is a fallback, not the normal path" requires.

    The caller uses this as a CLASSIFICATION OVERRIDE rather than an early return. That distinction
    was a bug once: returning here skipped the Conditional handling, so no pending slot was set and
    a user who had just said "because of security" was asked which ground applied on their very
    next message.

    AMBIGUITY BETWEEN INTENTS DISQUALIFIES THE OVERRIDE. If two intents both clear DIRECT_FLOOR,
    this returns None and lets the classifier decide, after which `lookup` is scoped to one intent
    and a cross-intent answer is impossible. The floor alone was sufficient only while one intent
    had seeds: it asks "is this close to a known question" and never asked "is it clearly closer to
    THIS intent's known question than to another's". Measured by `_direct_floor_eval.py` once a
    second intent had seeds -- "can I redeploy to my state of origin" scored 0.80 against
    posting_influence's state-of-origin seed and 0.62 against relocation's, so the override served a
    posting answer, and a posting follow-up, to a redeployment question. The verdict happened to
    match, the content and the rest of the conversation did not.

    BLOCKERS PARTICIPATE HERE, AND THAT IS DELIBERATE, because it cuts both ways and the protective
    direction is the one that matters. A blocker clearing the floor means the message is very close
    to a question we know we cannot answer, which is exactly the ambiguity the gate exists to
    respect: it makes `len(over)` two, suppresses the override, and hands the decision to the
    classifier, after which `lookup` is scoped to one intent. The cost is that a blocker can also
    disqualify an override that would have been right. Measured by `_direct_floor_eval.py`, which
    reports blocker wins in their own column so the trade is visible rather than assumed.
    """
    if not _ready or not message:
        return None
    scored = []
    for intent in _index:
        seed, score = _best(message, intent)
        scored.append((score, intent, seed))
    if not scored:
        return None
    over = [s for s in scored if s[0] >= DIRECT_FLOOR]
    if len(over) != 1:
        return None
    _, intent, seed = over[0]
    hit = _answers.get((intent, seed))
    return (intent, hit[0], hit[1]) if hit else None


def debug(message: str, intent: str, k: int = 3):
    """Top k (seed_id, similarity) for this message, for smoke tests. Ignores the floor."""
    if not _ready or intent not in _index:
        return []
    from sklearn.metrics.pairwise import cosine_similarity

    d = _index[intent]
    sim = (0.7 * cosine_similarity(d["word"].transform([message]), d["Iw"])
           + 0.3 * cosine_similarity(d["char"].transform([message]), d["Ic"]))[0]
    order = sorted(range(len(sim)), key=lambda i: -sim[i])
    seen, out = set(), []
    for i in order:
        seed = d["seeds"][i]
        if seed in seen:
            continue
        seen.add(seed)
        out.append((seed, round(float(sim[i]), 3)))
        if len(out) >= k:
            break
    return out
