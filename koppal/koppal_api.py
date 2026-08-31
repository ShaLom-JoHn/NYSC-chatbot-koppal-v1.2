"""
koppal_api.py -- thin HTTP layer over the dialogue engine.

Owns every reply-string convention in ONE place: the blank-line bubble split and the
" Back to your earlier question: " callback marker. The front end receives clean JSON and
never re-implements engine coupling. The engine, KB, classifier and chitchat modules are
imported and used UNCHANGED -- this file adds no answer behaviour.

Run:  uvicorn koppal_api:app --reload
Serves the JSON API under /api/* and the static front end (web/) at /.
"""
from __future__ import annotations

import copy
import csv
import os
import re
import threading
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import koppal_dialogue_manager as dm
import koppal_browse_map as bmap

# Phase 3's per-question answers. Optional by design: no sidecar, no seeds, and every reply
# falls back to the intent's chat_answer exactly as before.
try:
    import koppal_seeds as seeds
    _SEEDS_IMPORTED = True
except Exception:
    seeds = None
    _SEEDS_IMPORTED = False
_SEEDS_READY = False

# Classifier import guard -- mirrors reference/app.py so a missing model degrades to
# "everything is out_of_scope" instead of crashing the server.
try:
    import koppal_nlu as nlu
    _NLU_IMPORTED = True
except Exception:
    nlu = None
    _NLU_IMPORTED = False

KB_PATH = "data/koppal_knowledge_base.csv"
PARAPHRASE_PATH = "data/paraphrases.csv"
# The classifier's training set. Read ONLY to quote a real user question on the Browse
# full-answer page -- it never influences classification, and it is kept separate from
# PARAPHRASE_PATH so Home's tile labels keep using the curated list exactly as before.
SOURCE_PATH = "nysc_question_source-1.csv"
CONTRIB_PATH = "data/pending_contributions.csv"
WEB_DIR = "web"

# Rotating input hints. Verbatim from reference/koppal_theme.py:PLACEHOLDERS (the theme
# module is reference-only now; the list is small and canonical, so it lives here).
PLACEHOLDERS = [
    "when will they pay allawee",
    "can I change my PPA?",
    "how do i check my batch stream",
    "what does otondo mean",
    "am I allowed to customize my khaki?",
    "my name is not on the senate list",
    "do I need my original waec certificate at camp",
    "can I relocate to my husband's state",
]

CALLBACK_MARKER = " Back to your earlier question: "

# Intents that are never worth OFFERING as a "did you mean one of these?" chip, even
# when the classifier ranks one in the top 3. out_of_scope and noise have no answer to
# show, and start_over is a command rather than a topic.
UNSUGGESTABLE = {"out_of_scope", "noise", "start_over"}

# ---------------------------------------------------------------- milestone grouping
# The KB's 12 categories are too many to be a top level (spec A11.15), so the UI sees
# FIVE: four steps of the service year in order, plus one bucket for everything that
# isn't on the timeline. This is presentation only -- the KB's `category` column is
# never rewritten, and any category not named here falls into the last group.
MILESTONES = [
    ("Registration",     ["Registration & Eligibility"]),
    ("Orientation camp", ["Orientation Camp"]),
    ("Service year",     ["Posting & PPA", "Redeployment & Relocation",
                          "Working & Life During Service", "Allowance"]),
    ("Passing out",      ["Clearance", "Certificates & Documents", "End of Service"]),
    ("Good to know",     ["Special Circumstances", "Terms & Lookups", "General / Meta"]),
]

# ---------------------------------------------------------------- load-once state
KB: dict = {}
QUESTIONS: dict = {}   # intent -> [real user phrasings, from data/paraphrases.csv]
SOURCE_Q: dict = {}    # intent -> [real user questions, from the training set]
_NLU_READY = False

# Per-request scratch space for the classification the engine just asked for. Written by
# classify(), read by post_message(). Never returned as-is: the confidence label and the
# probabilities stay server-side (the spec's rule that answer_confidence never appears in
# a response), only intent names and labels go out.
_TURN = threading.local()


def _load_kb() -> dict:
    with open(KB_PATH, encoding="utf-8") as f:
        return {r["intent"]: r for r in csv.DictReader(f)}


def _load_source_questions() -> dict:
    """intent -> real user questions from the classifier's training set, shortest first.

    Used only to QUOTE a question on the Browse full-answer page. Shortest-first because
    the pool runs from "Are phones allowed in camp?" to three-line forum posts, and the
    short ones are the ones that read as a question someone would actually ask. Anything
    under 15 characters is a fragment, not a question, so it is dropped.
    """
    out: dict = {}
    try:
        with open(SOURCE_PATH, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                q = (r.get("question") or "").strip()
                if len(q) >= 15:
                    out.setdefault((r.get("intent") or "").strip(), []).append(q)
    except FileNotFoundError:
        return out
    for intent in out:
        out[intent].sort(key=lambda s: (len(s), s))
    return out


def _load_questions() -> dict:
    """Real user-phrased questions per intent. Used only to LABEL Home tiles and to
    give a tap something natural to ask -- it never influences classification."""
    out: dict = {}
    try:
        with open(PARAPHRASE_PATH, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                q = (r.get("paraphrase") or "").strip()
                if q:
                    out.setdefault((r.get("intent") or "").strip(), []).append(q)
    except FileNotFoundError:
        pass
    return out


def kb_lookup(intent: str):
    return KB.get(intent)


def classify(message: str):
    """(intent, "high"|"medium"|"low"). Falls back to out_of_scope when the model is
    unavailable, exactly as the reference front end did.

    Also records this turn's ranking on `_TURN` so post_message can offer the top 3
    when it refuses. The engine only ever receives the (intent, confidence) pair -- it
    stays unaware that a ranking exists, which is why the "did you mean" feature needs
    no engine change at all. Thread-local because FastAPI runs sync endpoints in a
    threadpool, so two requests can be in flight at once.
    """
    if not _NLU_READY:
        _TURN.ranked, _TURN.confidence = [], "low"
        return "out_of_scope", "low"
    intent, confidence = nlu.classify(message)
    # Memoised inside nlu on the same message classify() just scored, so this reads the
    # probability vector already computed rather than running the pipeline twice.
    _TURN.ranked, _TURN.confidence = nlu.top_intents(message, 3), confidence
    return intent, confidence


def _init():
    global KB, QUESTIONS, SOURCE_Q, _NLU_READY, _SEEDS_READY
    KB = _load_kb()
    QUESTIONS = _load_questions()
    SOURCE_Q = _load_source_questions()
    if _NLU_IMPORTED:
        try:
            nlu.load_model()
            _NLU_READY = True
        except Exception:
            _NLU_READY = False
    if _SEEDS_IMPORTED:
        try:
            _SEEDS_READY = bool(seeds.load())
        except Exception:
            _SEEDS_READY = False


# ---------------------------------------------------------------- sessions (in-memory)
# { session_id: {"state": ConversationState, "history": [deepcopy snapshots]} }
# Single-process only. Scaling path: serialise state to a signed cookie or move to Redis.
SESSIONS: dict = {}


def _session(session_id: str):
    s = SESSIONS.get(session_id)
    if s is None:
        s = {"state": dm.ConversationState(), "history": []}
        SESSIONS[session_id] = s
    return s


# ---------------------------------------------------------------- reply parsing (owned here)
def split_bubbles(text: str):
    """Blank line = new bubble. Ported from reference/app.py:split_bubbles."""
    return [c.strip() for c in re.split(r"\n\s*\n", (text or "").strip()) if c.strip()]


def branch_label(key: str) -> str:
    """`stage:after_camp` -> `after camp`. The slot prefix is scaffolding, not shown."""
    return key.split(":")[-1].replace("_", " ")


def has_more(intent: str) -> bool:
    """Offer the prose only when there's meaningfully more of it than the lead."""
    r = kb_lookup(intent)
    if not r:
        return False
    prose = (r.get("answer") or "").strip()
    lead = (r.get("chat_answer") or "").strip()
    return bool(prose) and len(prose) > len(lead) + 200


def _choices_from_pending(pending: Optional[dict], owner: Optional[str] = None):
    """Clickable choices for the current follow-up, or []. Handles the compound case the
    reference app missed: a compound sub-slot keeps its real type in sub_expected_type.

    `owner` is the intent the menu belongs to (`state.active_intent`) -- the pending dict
    itself doesn't record it. It rides along on every choice so a click can be TAGGED with
    the menu it came from (B10): the front end sends {intent, key} instead of the bare key
    as text, and the engine resolves it directly even after this follow-up has closed.
    """
    if not pending:
        return []
    et = pending.get("expected_type")
    effective = pending.get("sub_expected_type") if et == "compound" else et
    options = pending.get("options")
    owner = owner or ""
    if effective == "branch_select" and isinstance(options, dict) and "__slot__" not in options:
        return [{"key": k, "label": branch_label(k), "intent": owner} for k in options]
    if effective == "yes_no":
        return [{"key": "yes", "label": "yes", "intent": owner},
                {"key": "no", "label": "no", "intent": owner}]
    return []


def _pending_kind(pending: Optional[dict]):
    if not pending:
        return None
    et = pending.get("expected_type")
    if et == "compound":
        return pending.get("sub_expected_type") or "compound"
    return et


def _suggestions(state, pending):
    """The "did you mean one of these?" chips for this turn, or [].

    Cross-validated top-3 accuracy is 0.874 against top-1 0.716, so roughly 16% of
    questions have the right intent sitting at #2 or #3. Reading only #1 threw every one
    of them away. This changes nothing about what the classifier predicts -- it only stops
    discarding the part of its output that was already there.

    Offered on exactly one kind of turn: the engine has just refused a message it could not
    place, nothing is waiting on an answer, and the ranking is still worth reading.
    Deliberately NOT offered when:
      - a follow-up is open. The engine re-asks it, and chips for some other topic stacked
        under that question read as answers to it.
      - this is the second consecutive miss. The engine escalates to a firm out_of_scope
        there, and offering topics straight after "I can't help with that" contradicts it.
      - the top probability is below nlu.SUGGEST_FLOOR, where the ranking is noise and a
        refusal is the honest reply.
    """
    if not _NLU_READY or pending:
        return []
    if getattr(_TURN, "confidence", None) != "low":
        return []
    # 1 means this turn was the FIRST miss -- the "can you rephrase?" reply. The engine
    # resets the counter to 0 when it escalates on the second, so this reads as "we are on
    # the turn that asked the user to try again".
    if getattr(state, "consecutive_low_confidence", 0) != 1:
        return []
    ranked = getattr(_TURN, "ranked", None) or []
    if not ranked or ranked[0][1] < nlu.SUGGEST_FLOOR:
        return []
    out = []
    for intent, _prob in ranked:
        # No probabilities leave the API, only names. An intent with no KB row has nothing
        # to show if tapped, so it is never offered.
        if intent in UNSUGGESTABLE or not kb_lookup(intent):
            continue
        out.append({"intent": intent, "label": intent.replace("_", " ")})
    return out


def _forced_classifier(intent: str):
    """A classify_fn that always returns `intent` at high confidence.

    This is how a tapped suggestion is answered, and it needs no engine change: the engine
    already takes its classifier as a parameter precisely so it doesn't care where a
    classification comes from. The tap re-sends the user's ORIGINAL message with the picked
    intent attached, so everything downstream behaves exactly as it would have if the
    classifier had been confident about that intent the first time -- including
    _prematch_branch reading the user's own words to skip a follow-up it can already
    answer, which would have been lost had the chip sent its own label as the message.
    """
    def classify_fn(_message: str):
        _TURN.ranked, _TURN.confidence = [], "high"  # never suggest on top of a pick
        return intent, "high"
    return classify_fn


# ---------------------------------------------------------------- schemas
class MessageIn(BaseModel):
    session_id: str
    message: str
    # B10 -- a tagged click: {"intent": ..., "key": ...}. Present only when the message came
    # from a choice button, so the engine can resolve it against the menu it belongs to
    # instead of re-reading the key as if the user had typed it.
    #
    # A "did you mean" suggestion sends the same shape with NO key: {"intent": ...}. That
    # means "the user picked this topic for the message they already sent", and it is served
    # by forcing the classification rather than by looking up a branch.
    choice: Optional[dict] = None


class SessionIn(BaseModel):
    session_id: str


class ContributeIn(BaseModel):
    category: str = ""
    asked: str = ""
    wrong: str = ""


# ---------------------------------------------------------------- app
app = FastAPI(title="Koppal API")


@app.post("/api/message")
def post_message(inp: MessageIn):
    sess = _session(inp.session_id)
    state = sess["state"]
    sess["history"].append(copy.deepcopy(state))  # snapshot before mutating (undo)

    # A suggestion pick is a tag carrying an intent and no key (branch chips carry both).
    # It re-runs the user's original message with the classification forced, so the answer
    # is the one the tapped label promised. Unknown intents fall through to normal
    # classification rather than erroring, so a stale or hand-made tag is harmless.
    pick = inp.choice or {}
    picked_intent = pick.get("intent") if not pick.get("key") else None
    classify_fn = classify
    if picked_intent and kb_lookup(picked_intent):
        classify_fn = _forced_classifier(picked_intent)

    reply = dm.handle_message(inp.message, state, classify_fn, kb_lookup, inp.choice,
                              seeds.lookup if _SEEDS_READY else None,
                              # skipped on a forced pick: the user has already chosen the topic,
                              # so the intent-scoped lookup is the right one
                              (seeds.lookup_direct if _SEEDS_READY and not picked_intent else None))

    callback = None
    if CALLBACK_MARKER in reply:
        reply, callback = reply.split(CALLBACK_MARKER, 1)  # split callback off first

    texts = split_bubbles(reply)
    pending = state.pending_question
    trigger = (pending or {}).get("text", "").strip() if pending else ""
    answered = getattr(state, "last_answered_intent", None)

    bubbles = []
    more = None
    for i, text in enumerate(texts):
        last = i == len(texts) - 1
        kind = "answer"
        if trigger and last and text == trigger:
            kind = "ask"
        elif last and answered and has_more(answered):
            more = answered
        bubbles.append({"text": text, "kind": kind})

    if callback:
        bubbles.append({"text": "Back to your earlier question: " + callback.strip(),
                        "kind": "back"})

    suggestions = _suggestions(state, pending)
    if suggestions and bubbles:
        # The engine's refusal ("Can you rephrase that?") is the right words when there is
        # nothing to offer and the wrong ones sitting directly above three topics to pick
        # from. Rewriting it is presentation, so it happens here: the engine has no idea a
        # ranking exists, and keeping it that way is what made this a zero-engine-change
        # feature. The refusal itself is untouched whenever no suggestion qualifies.
        bubbles[-1] = {"text": "I'm not certain I follow. Did you mean one of these?",
                       "kind": "answer"}

    return {
        "bubbles": bubbles,
        "choices": _choices_from_pending(pending, getattr(state, "active_intent", None)),
        # Top-3 "did you mean one of these?" for a refused message. Same chip shape as
        # `choices` minus the branch key, and the two are mutually exclusive by
        # construction: choices need an open follow-up, suggestions need none.
        "suggestions": suggestions,
        "more": more,
        # what the conversation is currently ON -- drives the chat header's "still on X".
        # Same engine field as `more`, minus the has_more gate; still never the confidence.
        "topic": (answered or "").replace("_", " ") or None,
        # Which intent the OPEN follow-up belongs to. Distinct from `topic`: the engine
        # clears last_answered_intent on every non-answer turn (B11), so `topic` goes null
        # exactly when a slot is still open -- and the front end then had no way to say what
        # the choices were for. An off-topic message in the middle of a follow-up (owner's
        # bug 2: a relocation slot left open across "very good") left an unlabelled chip row
        # on screen, so the eventual pick read as an answer to nothing. Presentation only.
        "asking": (getattr(state, "active_intent", None) or "").replace("_", " ") or None,
        "pending": bool(pending),
        "pending_kind": _pending_kind(pending),
    }


def _demand(intent: str) -> int:
    """How many source questions mapped to this intent -- the KB's own popularity proxy."""
    try:
        return int((KB.get(intent, {}).get("question_count") or 0))
    except (TypeError, ValueError):
        return 0


def sample_questions(intent: str):
    """Real phrasings for this intent, or []. Deterministic order, so a tile label and the
    message its tap sends are always the same string."""
    return list(QUESTIONS.get(intent) or [])


def sample_question(intent: str):
    """A question for this intent -- a real stored phrasing when we have one, otherwise the
    intent's own words as a question. Never None, so "Ask in chat" can appear on EVERY
    topic instead of only the lucky ones (spec A11.6)."""
    qs = sample_questions(intent)
    if qs:
        return qs[0]
    return intent.replace("_", " ").strip() + "?"


def browse_question(intent: str):
    """The question quoted on the Browse full-answer page, in a user's own words.

    Order of preference: a hand-picked line for the 13 intents that were split out of a
    broader parent after the training set was built, then the curated paraphrase, then the
    shortest real training question. Only if all three are empty does it fall back to the
    intent's own words -- which is the vague label this whole layer exists to remove, so
    the fallback should stay unused.
    """
    fixed = bmap.QUESTION_OVERRIDES.get(intent)
    if fixed:
        return fixed
    qs = sample_questions(intent)
    if qs:
        return qs[0]
    src = SOURCE_Q.get(intent) or []
    if src:
        return src[0]
    return intent.replace("_", " ").strip() + "?"


def _milestone_of(category: str) -> str:
    for name, cats in MILESTONES:
        if category in cats:
            return name
    return MILESTONES[-1][0]      # anything unmapped is "not on the timeline"


@app.get("/api/milestones")
def get_milestones(per: int = 6):
    """The five top-level milestones, in service-year order, each with the KB categories it
    absorbs and up to `per` real questions drawn from its busiest intents. Drives both the
    Home board and the Browse spines."""
    buckets = {name: {"milestone": name, "step": i + 1, "categories": [], "topics": []}
               for i, (name, _) in enumerate(MILESTONES)}

    for intent, row in KB.items():
        cat = (row.get("category") or "").strip()
        if not cat or cat.startswith("NOISE"):
            continue
        if bmap.is_hidden(intent):
            continue          # machinery, not a topic anyone browses
        b = buckets[_milestone_of(cat)]
        if cat not in b["categories"]:
            b["categories"].append(cat)
        b["topics"].append({
            "intent": intent,
            "title": bmap.title_of(intent),
            "category": cat,
            "question": sample_question(intent),
            "_demand": _demand(intent),
            "_real": bool(sample_questions(intent)),
        })

    out = []
    for name, cats in MILESTONES:
        b = buckets[name]
        b["topics"].sort(key=lambda t: -t["_demand"])
        # the typewriter should read like a person asking, so prefer intents that have a
        # stored phrasing; title-shaped fallbacks only fill in if there aren't enough
        display = sorted(b["topics"], key=lambda t: (not t["_real"], -t["_demand"]))
        questions = [t["question"] for t in display[: max(1, per)]]
        for t in b["topics"]:
            t.pop("_demand", None)
            t.pop("_real", None)
        out.append({
            "milestone": b["milestone"],
            "step": b["step"],
            "categories": b["categories"],
            "questions": questions,
            "chapters": _milestone_chapters(cats, b["topics"]),
            "topics": b["topics"],
        })
    return out


def _milestone_chapters(cats, topics):
    """A milestone's topics as ONE level of chapters, in the order its categories are
    declared in MILESTONES.

    A milestone can hold several KB categories, and a category can hold chapters, which
    would nest two levels deep on one page. It is flattened instead: a chaptered category
    contributes its own chapters, and a small category contributes a single chapter named
    after itself. So every heading on the page is the same kind of thing, whether it came
    from a chapter map or from a category. Topics keep their map order, not demand order.
    """
    by_intent = {t["intent"]: t for t in topics}
    out = []
    for cat in cats:
        members = [i for i in KB if (KB[i].get("category") or "").strip() == cat
                   and i in by_intent]
        if not members:
            continue
        for chapter, group in bmap.chapters_for(cat, members):
            out.append({
                "chapter": chapter or cat,
                "category": cat,
                "topics": [by_intent[i] for i in group],
            })
    return out


@app.get("/api/categories")
def get_categories():
    counts: dict = {}
    for intent, row in KB.items():
        cat = (row.get("category") or "").strip()
        if cat and not cat.startswith("NOISE") and not bmap.is_hidden(intent):
            counts[cat] = counts.get(cat, 0) + 1
    ordered = sorted(counts.items(), key=lambda kv: -kv[1])
    return [{"category": c, "count": n} for c, n in ordered]


@app.get("/api/highlights")
def get_highlights(n: int = 5, per: int = 4):
    """Home gallery: the n busiest categories, each with up to `per` real questions drawn
    from data/paraphrases.csv (most-asked first). A live tile cycles through `picks`; a tap
    sends the question currently shown. Empty `picks` means that tile falls back to Browse."""
    buckets: dict = {}
    for intent, row in KB.items():
        cat = (row.get("category") or "").strip()
        if not cat or cat.startswith("NOISE") or bmap.is_hidden(intent):
            continue
        b = buckets.setdefault(cat, {"category": cat, "count": 0, "cands": []})
        b["count"] += 1
        for q in sample_questions(intent):
            b["cands"].append((_demand(intent), intent, q))

    out = []
    for b in sorted(buckets.values(), key=lambda e: -e["count"])[: max(1, n)]:
        picks, seen = [], set()
        for demand, intent, q in sorted(b["cands"], key=lambda t: -t[0]):
            if intent in seen:            # one question per intent, so a tile isn't repetitive
                continue
            seen.add(intent)
            picks.append({"intent": intent, "title": bmap.title_of(intent),
                          "question": q, "asked": demand})
            if len(picks) >= max(1, per):
                break
        out.append({"category": b["category"], "count": b["count"], "picks": picks})
    return out


@app.get("/api/category/{name}")
def get_category(name: str):
    """One category's topics, grouped into chapters.

    `chapters` is the shape the Browse category page renders: [{chapter, topics}]. For the
    nine small categories there is a single group with `chapter: null`, so one code path
    draws both. `topics` repeats the same rows flat, in the same order, for any caller that
    just wants the list. Topic order inside a chapter is the map's authored order, not
    alphabetical -- a contents page reads in a deliberate sequence.
    """
    intents = [i for i, r in KB.items()
               if (r.get("category") or "").strip() == name and not bmap.is_hidden(i)]
    if not intents:
        raise HTTPException(status_code=404, detail="unknown category")

    def topic(i):
        return {
            "intent": i,
            "title": bmap.title_of(i),
            "lead": (KB[i].get("chat_answer") or "").strip(),
            "asked": _demand(i),
            "branches": bool((KB[i].get("follow_up_answer") or "").strip()),
        }

    chapters = [{"chapter": ch, "topics": [topic(i) for i in members]}
                for ch, members in bmap.chapters_for(name, intents)]
    return {
        "category": name,
        "chapters": chapters,
        "topics": [t for c in chapters for t in c["topics"]],
    }


# Intents whose branch text lives in the ENGINE, not in the KB's follow_up_answer column.
# `ppa_course_matching` asks a free-text question ("what's your course of study?") and resolves
# the reply through COURSE_BUCKET_MAP (97 courses) into COURSE_BUCKET_REPLIES (10 buckets), so
# chat works -- but Browse derives its branches from the KB column, which is empty here, so the
# topic page showed a question with no answers under it. Reading the engine's own dict keeps ONE
# source of truth; copying the ten replies into the CSV would immediately start drifting.
# Same precedent as _branch_groups reading COMPOUND_SLOTS for its per-slot questions.
_ENGINE_BRANCHES = {
    "ppa_course_matching": lambda: dm.COURSE_BUCKET_REPLIES,
}


def _branch_groups(intent: str, branches, trigger: str):
    """Branches split into the questions they actually answer.

    A compound intent asks two things at once, and its branch keys carry the slot they
    belong to (`ground:health`, `stage:in_camp`). COMPOUND_SLOTS already holds a short
    written question per slot, so each group can be headed by its own question instead of
    dumping every branch under one run-on trigger sentence. Nothing is authored here.

    A single-slot intent comes back as one group headed by its trigger. A slot with no
    branch keys at all (a free-text one, like "which state?") is skipped -- a question with
    no options is a dead end on a page you cannot type into.
    """
    slots = dm.COMPOUND_SLOTS.get(intent)
    if not slots:
        return [{"slot": None, "ask": trigger, "branches": branches}] if branches else []

    out, claimed = [], set()
    for s in slots:
        mine = [b for b in branches if b["key"].split(":")[0] == s["name"]]
        if mine:
            claimed.update(b["key"] for b in mine)
            out.append({"slot": s["name"], "ask": (s.get("ask") or trigger), "branches": mine})
    spare = [b for b in branches if b["key"] not in claimed]
    if spare:
        out.append({"slot": None, "ask": trigger, "branches": spare})
    return out


@app.get("/api/intent/{intent}")
def get_intent(intent: str):
    r = kb_lookup(intent)
    if not r:
        raise HTTPException(status_code=404, detail="unknown intent")
    branches_raw = dm._parse_branches(r.get("follow_up_answer", "") or "")
    branches = [{"key": k, "label": branch_label(k), "text": t}
                for k, t in branches_raw.items()]
    if not branches and intent in _ENGINE_BRANCHES:
        branches = [{"key": k, "label": k, "text": t}
                    for k, t in _ENGINE_BRANCHES[intent]().items()]
    cat = (r.get("category") or "").strip()
    trigger = (r.get("follow_up_trigger") or "").strip()
    # answer_confidence is deliberately never returned.
    return {
        "intent": intent,
        "category": cat,
        # the chapter, not the category, is what the page shows under its title: the back
        # control above already names the level up, so repeating it there said nothing
        "chapter": bmap.chapter_of(cat, intent),
        "title": bmap.title_of(intent),
        "lead": (r.get("chat_answer") or "").strip(),
        "trigger": trigger,
        "branches": branches,
        "groups": _branch_groups(intent, branches, trigger),
        "prose": (r.get("answer") or "").strip(),
        "has_more": has_more(intent),
        # `question` is what "Ask in chat" sends. `asked_as` is the same question shown as a
        # quotation on the page -- a real user's wording, where `trigger` is the engine's.
        "question": sample_question(intent),
        "asked_as": browse_question(intent),
        "asked": _demand(intent),
    }


@app.get("/api/placeholders")
def get_placeholders():
    return PLACEHOLDERS


@app.get("/api/health")
def get_health():
    return {"classifier_available": _NLU_READY}


@app.post("/api/contribute")
def post_contribute(inp: ContributeIn):
    parent = os.path.dirname(CONTRIB_PATH)
    if parent:
        os.makedirs(parent, exist_ok=True)
    new = not os.path.exists(CONTRIB_PATH)
    with open(CONTRIB_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["timestamp", "category", "asked", "wrong"])
        w.writerow([datetime.now(timezone.utc).isoformat(), inp.category, inp.asked, inp.wrong])
    return {"ok": True}


@app.post("/api/session/reset")
def post_reset(inp: SessionIn):
    sess = _session(inp.session_id)
    sess["state"].clear()
    sess["history"] = []
    return {"ok": True}


@app.post("/api/session/undo")
def post_undo(inp: SessionIn):
    sess = _session(inp.session_id)
    if sess["history"]:
        sess["state"] = sess["history"].pop()
        return {"ok": True}
    return {"ok": False}


_init()

# Static front end LAST, so /api/* routes are matched first. Guarded so the API still
# boots for testing before web/ exists.
if os.path.isdir(WEB_DIR):
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
