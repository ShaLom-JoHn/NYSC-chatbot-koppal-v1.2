---
title: Koppal
emoji: 🇳🇬
colorFrom: green
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
---

# Koppal

An NYSC question answering assistant. Two parts: a text classification model that works out what a
question is about, and an application built around it that holds a conversation and gives the answer.

**Try it: [LIVE URL GOES HERE]** — open the link and type a question. Nothing to install.

Suggested questions to try:

- `how much is allawee` — informal spelling, the model still routes it, then answer the follow up with
  `the regular monthly cycle` to see it use the earlier question
- `can i change my ppa` — a direct answer with the actual steps
- `my allowance has not been paid` — the app asks a clarifying question before committing
- `who won the last election` — out of scope, and it says so rather than inventing an answer

---

# Part 1: The model

## What it does

It takes one question and predicts which of **121 topics** it belongs to. The topic is called an
**intent**. Nothing is generated: once the intent is known, the answer is looked up from text written
by hand. A wrong answer is therefore a real answer filed under the wrong topic, not invented text.

- **Type:** multi-class text classification, 121 classes
- **Features:** TF-IDF over word 1 to 2 grams, combined with TF-IDF over character 3 to 5 grams
- **Classifier:** Logistic Regression, `C=10.0`, one pipeline saved as a single file
- **Trained on:** 1,480 real questions, plus 184 hand written paraphrases for the rarest topics
- **Size:** 25 MB, loads once at startup, no GPU, no external API calls

The full build is in [koppal_intent_classifier.ipynb](koppal_intent_classifier.ipynb), which loads the
data, cleans it, explores it, compares three models, tunes the chosen one, evaluates it, and saves it.

## Results

Trained on 80% of the questions, tested on the 295 it had never seen.

| Measure | Score | What it means |
| --- | --- | --- |
| Accuracy | 0.742 | Out of 100 new questions it picks the right topic first time for 74 |
| Macro-F1 | 0.663 | The same idea, but each of the 121 topics counts equally, so a topic with 3 questions matters as much as one with 119. Lower than accuracy because the rare topics are the hard ones |
| Top-3 accuracy | 0.912 | The right topic is in its top three guesses 91 times out of 100, so when it is wrong it is usually only just wrong |
| Log loss | 1.356 | How well the confidence numbers are calibrated, which the next section depends on |

Those are from one split, which could be a favourable draw. Cross validated over 5 folds:

| Measure | Mean ± std |
| --- | --- |
| Accuracy | 0.721 ± 0.017 |
| Macro-F1 | 0.652 ± 0.026 |

The **± 0.026** is the more useful figure. It is the margin of error, and any future change that moves
macro-F1 by less than roughly twice it is not an improvement, only a different draw of test questions.

## It declines to answer rather than guessing

Every prediction carries a confidence value. Below **0.25** the app stops committing to one answer and
offers three topics to choose from instead. At that setting it answers about 75% of questions and is
right about 82% of the time when it does.

Lowering the bar to 0.10 raises coverage to 93% but accuracy only to 77%, so the extra coverage is
mostly guesses. Raising it to 0.50 gets 88% correct but answers fewer than half of all questions, which
reads as an assistant that will not help. Top-3 accuracy of 0.912 is what makes the middle option work:
a question below the threshold is not a dead end, it becomes three choices that usually contain the
right one.

## What made the model work

Measured by removing one component at a time and re-testing, in notebook section 10.3:

| Setup | Macro-F1 |
| --- | --- |
| Word features only | 0.168 |
| Character features only | 0.305 |
| Both, default settings | 0.496 |
| Both, tuned settings | **0.663** |

**Neither feature type works alone.** Word features on their own score 0.168. Character features on
their own score 0.305. Together they reach 0.496 before any tuning, which is far more than either.

**Character features are the stronger half.** Real questions are full of `corper`, `allawee`,
`callup`, `wen`. To a word matcher every one of those is a word it has never seen, worth nothing. A
character matcher still sees that `allawee` and `allowance` share `all` and `llo`, so the question lands
near the right topic anyway. This matters more here than it would elsewhere because the questions are
short, with a median of 12 words, so one unrecognised word is a large share of the input.

**Tuning contributed about as much as the features.** Raising `C` to 10 took the model from 0.496 to
0.663.

**Complement Naive Bayes beat Logistic Regression before tuning**, 0.560 against 0.496. Logistic
Regression was still chosen, because it has settings worth tuning that Naive Bayes does not, and
because it produces the calibrated confidence values the threshold above depends on. Tuned, it finishes
well ahead.

## How this version differs from the previous one

The previous model was trained on 23 August. Since then **164 of the 1,494 questions were relabelled**
and 17 were added, as topics that had grown too broad were split apart. The largest moves were all from
a large topic into a smaller, more specific one: 19 questions from `relocation_general_process` to
`post_relocation_process`, 14 from `posting_influence` to `ppa_course_matching`, 12 from
`batch_stream_timing` to `portal_open_registration_window`.

| | Previous | This version |
| --- | --- | --- |
| Accuracy | 0.736 | 0.742 |
| Macro-F1 | 0.668 | 0.663 |
| Top-3 accuracy | 0.901 | 0.912 |
| Best settings | `C=8.0`, `class_weight="balanced"` | `C=10.0`, `class_weight=None` |

**The scores did not move.** Every difference above is well inside the ± 0.026 margin of error, so none
of them is a real change. What did change is that the model now predicts the topics the knowledge base
actually has. The old model was trained against a taxonomy that 164 questions had since moved away from,
so it was routing correctly to labels that no longer meant the same thing.

**One finding is worth reporting because it reverses the previous conclusion.** In the old model
`class_weight="balanced"` was the single biggest lever, worth about +0.11 macro-F1, because the two
largest topics were absorbing questions that belonged to smaller ones. In this version the setting has
**no measurable effect at all**: 0.663 against 0.655, a gap smaller than the margin of error.

The explanation is that the relabelling fixed the problem in the data that the setting was compensating
for. Those 164 moves took questions out of the large topics and put them in the specific ones they
belonged to. Once the labels were right, the correction was no longer needed. That is a better outcome
than a tuning win, because it holds regardless of which classifier is used.

---

# Part 2: Koppal

The model answers one question: *what is this about?* Koppal is everything built around that answer to
make it useful to somebody who is actually trying to get through their service year.

The name is from **kopa**, what Nigerian corps members call each other.

## Why the model alone is not enough

A classifier that returns `allowance_amount` has not helped anyone yet. Four things have to happen
around it.

**Someone has to have written the answer.** The knowledge base is 134 hand written entries covering
registration, call-up letters, camp, posting, relocation, allowances, clearance and certificates.

**One answer per topic is often too coarse.** *"How much is the allowance"* and *"when does it get
paid"* are the same topic and different questions. A single answer for the topic has to either cover
both and be too long, or pick one and be wrong for the other.

**Questions arrive in the middle of a conversation.** *"What about after camp?"* means nothing on its
own. It has to be read against whatever was asked before it.

**Some questions cannot be answered without asking one back.** *"Can I still mobilise?"* depends on
whether the person was ever registered, and answering before knowing produces a confidently wrong
answer.

## The four layers

**1. Classification — `koppal_nlu.py`**
Loads the model once, returns the intent and a confidence band. Above 0.25 the answer is given, below
it the top three topics are offered as choices, and below 0.10 nothing is offered because even the
suggestions would be noise.

**2. Dialogue — `koppal_dialogue_manager.py`**
Holds the conversation. It tracks what was asked before, so a follow up is read in context. It asks
clarifying questions and remembers the answer, so a reply of just *"yes"* resolves against the question
that was pending. It handles corrections, so *"no I meant Lagos"* revises the previous turn rather than
starting over. And when a new topic interrupts an unfinished one, it returns to the first afterwards
instead of dropping it.

**3. Answers — `data/koppal_knowledge_base.csv` and `data/question_answers.csv`**
Two levels. The knowledge base holds one short answer per topic, with a longer version behind it for
readers who want the detail. On top of that sits a **per-question layer**: 297 answers written for
specific questions rather than for topics, matched by text similarity within the predicted intent. When
a question matches one of those closely enough, it gets an answer written for exactly it. When nothing
matches, the topic's answer is used, which is the behaviour with the layer switched off. It currently
covers 694 of the 1,494 collected questions.

**4. Interface — `koppal_api.py` and `web/`**
One process serves a small JSON API and a static front end. The front end is plain HTML, CSS and
JavaScript with no build step and no framework, with light and dark modes.

## What a turn actually does

```
"how much is allawee"
        |
   koppal_nlu.classify()          -> allowance_amount, confidence 0.26
        |
   koppal_seeds.lookup()          -> is there an answer for THIS question?  no
        |
   knowledge base, allowance_amount
        |
   "The federal allowance is #77,000 a month, the same for every corps member,
    normally paid between the 25th and 30th. Any state or PPA top-up is extra
    and not guaranteed."
```

The answer is resolved in a fixed order: the per-question answer if one matches, then a branch answer
if a clarifying question is open, then the topic's short answer, then its long form. Each step falls
through to the next, so removing any layer degrades the reply rather than breaking it.

---

# Running it

## Nothing to install

Open the live link at the top of this file. That is the whole process.

## Locally, in a browser

```bash
pip install -r requirements.txt
uvicorn koppal_api:app
```

Then open `http://localhost:8000`. One process serves both the API and the front end, so there is
nothing else to start.

## Locally, in a terminal

```bash
python koppal_main.py
```

Same engine, no browser. Type `quit` to leave.

## The notebook

Open `koppal_intent_classifier.ipynb`. It is committed with its outputs, so every table and chart is
visible without running anything. Running it end to end retrains the model and overwrites
`model/koppal_classifier.pkl`.

To change the notebook, edit `_build_notebook.py` and run it, then `_execute_notebook.py` to run every
cell and write the outputs back in. Editing the notebook JSON directly is not the intended path.

---

# What is in this repository

Only what runs. The development history, audit scripts and working notes are kept out deliberately.

| Path | What it is |
| --- | --- |
| `koppal_intent_classifier.ipynb` | The model: data, EDA, selection, tuning, evaluation, saving |
| `_build_notebook.py` | Generates the notebook above |
| `model/koppal_classifier.pkl` | The trained pipeline, loaded at startup |
| `nysc_question_source-1.csv` | The dataset, 1,494 collected questions with their topics |
| `data/koppal_knowledge_base.csv` | The answers, one entry per topic |
| `data/question_answers.csv` | The per-question answers, 297 of them |
| `data/paraphrases.csv` | Hand written extra examples for the rarest topics |
| `koppal_nlu.py` | Loads the model, classifies, bands the confidence |
| `koppal_dialogue_manager.py` | Conversation state, follow ups, corrections, interrupted topics |
| `koppal_seeds.py` | Matches a question to a per-question answer |
| `koppal_chitchat.py` | Greetings and small talk, kept out of the model |
| `koppal_browse_map.py` | Structure for browsing topics rather than asking |
| `koppal_api.py` | The JSON API, and serves the front end |
| `koppal_main.py` | Terminal version |
| `web/` | The front end: one HTML file, one stylesheet, one script |
| `Dockerfile` | For the deployed version |

# Limitations

**Thin topics are the main one.** 36 of the 121 topics have fewer than 5 training questions, and the
notebook shows these are where the model performs worst. This is a data collection problem. No amount of
tuning fixes it and more questions is the only real answer.

**Six topics are not tested at all.** They have exactly one question each, so they cannot be split
across a training and a test set. They are trained on and their scores are unknown.

**Adjacent topics are genuinely ambiguous.** *"How do I relocate"* and *"what do I do after
relocating"* are separate topics that a human labeller could reasonably confuse. Some of the remaining
error is not recoverable without redefining the topics.

**One known routing defect.** The per-question matcher can answer before the classifier is consulted
when a question closely matches a known one. For 51 questions that do not yet have their own answer,
this fires on a near neighbour from a different topic and answers from the wrong one. The classifier
routes 39 of those correctly on its own, so the override is making it worse for them. The fix is a
subject check on that path and it is not yet applied.

**Answer coverage is partial.** 694 of the 1,494 collected questions have an answer written for them
specifically. The rest fall back to their topic's answer, which is correct but less precise.

**Sessions are held in memory.** Conversation state lives in the server process, so it is lost on
restart and the app runs as a single instance. Fine at this scale, and the path to more is to move that
store out of the process.

**The contribute form is unauthenticated.** Anyone using the deployed app can append a row to a file
reporting a wrong answer. It holds no personal data and the deployed filesystem resets on restart, but
it is an open write endpoint and worth knowing about.

# Licence

Two licences, because the code and the data are not the same kind of work.

**Code, Apache License 2.0.** Every source file here, the notebook included. See `LICENSE`. Apache-2.0
rather than MIT for the express patent grant and because it requires anyone modifying the code to say
that they did.

**Data, all rights reserved.** `nysc_question_source-1.csv`, `data/koppal_knowledge_base.csv`,
`data/question_answers.csv` and `data/paraphrases.csv`. See `data/LICENSE`. No copying, redistribution,
or use as training data for a released model without prior written permission. Reading it, running it
locally, and academic assessment of this project are all allowed.

Koppal is an independent project. It is not affiliated with, endorsed by, or an official channel of the
National Youth Service Corps. Answers are compiled from public sources and can go out of date. Confirm
anything that matters with NYSC directly.
