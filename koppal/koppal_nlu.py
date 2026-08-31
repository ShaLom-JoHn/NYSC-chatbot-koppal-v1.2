"""
nlu.py -- loads the trained TF-IDF + LogReg/SVM pipeline, predicts intent
+ confidence. No NYSC content, no dialogue logic -- just "what did the
classifier think this message was, and how sure is it."

Model file expected at model/koppal_classifier.pkl -- a single sklearn
Pipeline (TfidfVectorizer + LogisticRegression or SVC(probability=True)),
saved with joblib. dialogue_manager.py only ever calls classify_fn(message)
and gets back (intent, confidence_label) -- it never touches sklearn
directly, so swapping LogReg for SVM or retraining doesn't change anything
outside this file.
"""

import joblib

MODEL_PATH = "model/koppal_classifier.pkl"

# Confidence bucketing -> (intent, "high"|"medium"|"low"). The dialogue manager
# answers on BOTH high and medium and only falls back on low, so
# MEDIUM_CONFIDENCE_THRESHOLD is the real answer-vs-fallback floor. It is set
# from the classifier notebook's floor sweep (section 11, held-out set): 0.25
# is the knee -- about 62% of questions answered, about 81% right when
# answered. Going lower buys little (precision flattens near 77%); going higher
# silences too much. HIGH_CONFIDENCE_THRESHOLD is kept as a tier label for
# callers that want it, but does not change routing (medium answers like high).
HIGH_CONFIDENCE_THRESHOLD = 0.5
MEDIUM_CONFIDENCE_THRESHOLD = 0.25

# Below MEDIUM_CONFIDENCE_THRESHOLD the engine refuses. SUGGEST_FLOOR splits that
# refusal band in two: at or above it the top 3 are worth OFFERING (top_intents below),
# under it the ranking is noise and a plain refusal is the honest reply. The band exists
# because cross-validated top-3 accuracy is 0.874 against top-1 0.716 -- about 16% of
# questions have the right intent sitting at #2 or #3, and reading only #1 threw every
# one of them away.
#
# 0.10 is measured OUT OF FOLD, not guessed. `_suggest_floor.py` reuses the 5-fold
# construction from `_fold_candidates.py` (same seed, paraphrases added per fold train-side
# only) and scores every question once with a model that never saw it:
#
#     band         n   share   top1 right   truth in top 3
#     0.00-0.05   39    2.7%      23.1%         46.2%
#     0.05-0.10  148   10.2%      35.8%         56.8%
#     0.10-0.15  146   10.0%      52.1%         76.7%
#     0.15-0.20  132    9.1%      62.9%         85.6%
#     0.20-0.25  103    7.1%      65.0%         92.2%
#
# The headline is the size of the refusal band: 39% of real questions land under 0.25, and
# 74.3% of those have the right intent in their top 3. That is what reading only #1 threw
# away. (It cross-checks against the notebook's independent "answers ~62%" figure -- 61%
# answered here.)
#
# Floor 0.10 offers on 381 of the 568 refusals with the truth among the three 84.0% of the
# time; 0.15 offers on 235 at 88.5%; 0.05 on 529 at 76.4%.
#
# 0.15 was shipped first, on the argument that the in-sample table flattered the 0.10-0.15
# band. It did not -- in-sample said 76.5% there, out of fold says 76.7%. The real reason to
# include the band is the marginal exchange: it rescues 112 questions at the cost of 34
# offers where none of the three labels is what was asked, 3.3 to 1. A right offer converts
# a dead end into an answer; a wrong offer costs a glance and leaves the user exactly where
# a refusal already left them. Under 0.10 that ratio decays fast (0.05-0.10 is 56.8%, and
# that is also where genuinely off-topic messages land, where Phase 1's refusal net should
# win).
#
# Still not the same trade as lowering MEDIUM_CONFIDENCE_THRESHOLD to 0.10: down there #1
# alone is right 52.1%, and the bot would state it as fact instead of offering a choice.
SUGGEST_FLOOR = 0.10

_model = None  # loaded lazily so importing this module doesn't require the pkl to exist yet

# One-entry memo, {message: [(intent, prob), ...]}. A single turn asks for the label
# (classify) and, when the answer is refused, the top 3 (top_intents). Both read the
# same probability vector, so without this the model would vectorise and score the
# same string twice per turn. Keyed on the exact message; a new message evicts it.
_scored_message = None
_scored_ranking = None


def load_model(path: str = MODEL_PATH):
    """Load the trained pipeline from disk. Call once at startup (main.py)."""
    global _model, _scored_message, _scored_ranking
    _model = joblib.load(path)
    _scored_message = None  # a different model would make a cached ranking a lie
    _scored_ranking = None
    return _model


def _rank(message: str):
    """[(intent, probability), ...] over every trained intent, highest first.

    Raises the same errors classify() does rather than guessing, so a missing model or a
    pipeline without predict_proba fails loudly in one place.
    """
    global _scored_message, _scored_ranking
    if _model is None:
        raise RuntimeError("nlu._rank() called before load_model(). Call nlu.load_model() at startup.")
    if _scored_ranking is not None and _scored_message == message:
        return _scored_ranking

    # predict_proba requires probability=True on SVC; LogisticRegression has
    # it by default. If a pipeline is swapped in without it, fail loudly
    # instead of guessing a confidence.
    if not hasattr(_model, "predict_proba"):
        raise RuntimeError(
            "Loaded model has no predict_proba -- if using SVC, it must be "
            "instantiated with probability=True."
        )

    proba = _model.predict_proba([message])[0]
    ranking = sorted(zip((str(c) for c in _model.classes_), (float(p) for p in proba)),
                     key=lambda pair: pair[1], reverse=True)
    _scored_message, _scored_ranking = message, ranking
    return ranking


def top_intents(message: str, k: int = 3):
    """The k most likely intents as [(intent, probability), ...], highest first.

    For the "did you mean one of these?" offer. Presentation decisions -- whether the
    band qualifies, what to label a chip -- belong to the caller (koppal_api.py); this
    only reports what the classifier thinks. Empty message returns [] rather than a
    ranking over nothing, matching classify()'s early exit.
    """
    message = message.strip()
    if not message:
        return []
    return _rank(message)[:max(0, k)]


def classify(message: str):
    """
    Returns (intent: str, confidence: "high"|"medium"|"low").

    Requires load_model() to have been called first (main.py does this
    once at startup). Raises RuntimeError otherwise rather than silently
    predicting on nothing.
    """
    if _model is None:
        raise RuntimeError("nlu.classify() called before load_model(). Call nlu.load_model() at startup.")

    message = message.strip()
    if not message:
        return "out_of_scope", "low"

    intent = str(_model.predict([message])[0])

    # Ranked probabilities, shared with top_intents via the memo. The intent label still
    # comes from predict() so this function's behaviour is byte-identical to before the
    # ranking was added -- predict() is argmax over the same probabilities for this
    # pipeline, so ranking[0] is normally `intent`, but predict() stays the authority.
    top_confidence = _rank(message)[0][1]
    if top_confidence >= HIGH_CONFIDENCE_THRESHOLD:
        confidence = "high"
    elif top_confidence >= MEDIUM_CONFIDENCE_THRESHOLD:
        confidence = "medium"
    else:
        confidence = "low"

    return intent, confidence
