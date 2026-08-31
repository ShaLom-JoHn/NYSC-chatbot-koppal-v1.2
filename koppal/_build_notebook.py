"""Generates koppal_intent_classifier.ipynb. Edit THIS, never the notebook JSON.

The notebook is the graded ML deliverable, so it is written for somebody reading it once,
top to bottom, who wants to understand what was done and why. That drives three rules:

  1. Flat code. No helper functions that assemble a model somewhere the reader cannot see.
     `make_pipeline(make_union(word, char), clf)` written out is standard sklearn and shows
     the whole model in one place.
  2. Every metric earns its place by answering a question about the app. top-3 accuracy is
     in because the app offers three suggestion chips. log_loss is one line, not a section.
  3. Plain words. "How often is the right topic in the three we show" beats "top-k accuracy
     under the argsort of decision_function".

Run: python _build_notebook.py       then: python _execute_notebook.py
"""
import json

CELLS = []


def md(text):
    CELLS.append({"cell_type": "markdown", "metadata": {}, "source": text.strip("\n").split("\n")})


def code(text):
    CELLS.append({"cell_type": "code", "execution_count": None, "metadata": {},
                  "outputs": [], "source": text.strip("\n").split("\n")})


# ----------------------------------------------------------------- title
md("""
# Koppal, the NYSC question classifier

This notebook builds a text classification model. The model takes a question about the Nigerian
NYSC scheme and predicts which of 122 topics it belongs to. Those topics are called **intents**.
Once the intent is known, the answer is a straightforward lookup in a knowledge base.

An example of the problem: a user types *"how much is allawee"*. The model has to route that to
the monthly allowance topic, not to camp and not to relocation, despite the misspelling and the
missing question mark.

### Contents

1. Setup
2. Loading the data
3. Cleaning the data
4. Building the training set
5. Exploratory data analysis
6. Feature extraction
7. Train and test split
8. Model selection
9. Training the model
10. Hyperparameter tuning
11. Model evaluation
12. Confidence threshold tuning
13. Cross validation
14. Saving the model
15. End to end test
16. Summary of results
""")
md("""
## 1. Setup

Four libraries do all the work. `pandas` holds the data as a table, `matplotlib` draws,
`scikit-learn` is the machine learning, and `joblib` saves the finished model to a file.
""")

code("""
import pandas as pd
import matplotlib.pyplot as plt
import joblib

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import make_pipeline, make_union
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import ComplementNB, MultinomialNB
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.metrics import (accuracy_score, f1_score, classification_report,
                             confusion_matrix, top_k_accuracy_score, log_loss)

%matplotlib inline

# Fixing the random seed means the split and the training come out the same every run,
# so any change in a score is a real change and not luck.
RANDOM_STATE = 42

DATA_PATH  = "nysc_question_source-1.csv"
KB_PATH    = "data/koppal_knowledge_base.csv"
MODEL_PATH = "model/koppal_classifier.pkl"
""")

# ----------------------------------------------------------------- load
md("""
## 2. Loading the data

One CSV, one row per question. The two columns that matter are `question` (what somebody
typed) and `intent` (the topic it belongs to). Everything else in the file is sourcing notes
from when the dataset was built.
""")

code("""
raw = pd.read_csv(DATA_PATH)

print("rows in the file :", len(raw))
print("columns          :", list(raw.columns))
raw[["question", "intent"]].head(8)
""")

# ----------------------------------------------------------------- cleaning
md("""
## 3. Cleaning the data

Four things get removed, and each one would cause a specific problem if it stayed.

- **Blank rows.** A question with no text, or a question with no topic, teaches nothing.
- **Whitespace.** `"camp kit "` and `"camp kit"` are the same question to a human and two
  different questions to a computer, so both ends get trimmed.
- **The `noise_nonquestion` rows.** These are greetings, thanks and typing noise. They are
  in the dataset on purpose so the collection is honest, but they are not questions about
  NYSC, so training on them would teach the model to route small talk into real topics.
- **Empty strings left after trimming**, which is what `"   "` becomes.
""")

code("""
df = raw[["question", "intent"]].copy()

before = len(df)
df = df.dropna()
print("dropped blank rows           :", before - len(df))

df["question"] = df["question"].str.strip()
df["intent"] = df["intent"].str.strip()

before = len(df)
df = df[df["intent"] != "noise_nonquestion"]
print("dropped small talk and noise :", before - len(df))

before = len(df)
df = df[(df["question"] != "") & (df["intent"] != "")]
print("dropped empty after trimming :", before - len(df))

df = df.reset_index(drop=True)
print()
print("usable questions :", len(df))
print("topics (intents) :", df["intent"].nunique())
""")

# ----------------------------------------------------------------- training set
md("""
## 4. Building the training set

Supervised learning needs two things: the input and the correct answer. Here the input is the
question text and the correct answer is the intent. By convention these are named `X` and `y`.

No transformation happens in this step. It is separated out because this is the point where the
data stops being a spreadsheet and becomes a machine learning problem with a defined input and
a defined target.
""")

code("""
X = df["question"]     # the input:  what the user typed
y = df["intent"]       # the target: the topic it should be routed to

print("X:", X.shape, "-> example:", repr(X.iloc[0]))
print("y:", y.shape, "-> example:", repr(y.iloc[0]))
""")

# ----------------------------------------------------------------- EDA
md("""
## 5. Exploratory data analysis

Three properties of the dataset are measured here, because each one determines a decision later
in the notebook: how the questions are distributed across topics, how long a question is, and
whether the labelling is internally consistent.

### 5.1 Distribution of questions across topics
""")

code("""
per_intent = df["intent"].value_counts()

print("largest topic :", per_intent.index[0], "with", per_intent.iloc[0], "questions")
print("smallest topic:", per_intent.index[-1], "with", per_intent.iloc[-1], "questions")
print("median topic  :", int(per_intent.median()), "questions")
print()
print("topics with fewer than 5 questions:", (per_intent < 5).sum(), "of", len(per_intent))

per_intent.head(20).sort_values().plot(kind="barh", figsize=(8, 6), color="#4a7c59")
plt.title("The 20 largest topics")
plt.xlabel("questions")
plt.tight_layout()
plt.show()
""")

md("""
The dataset is **imbalanced**: the number of questions per topic varies by more than an order of
magnitude. `relocation_general_process` has over a hundred questions and dozens of topics have
fewer than five.

The consequence for training is that a model can score well by learning the large topics and
ignoring the small ones, because predicting a popular topic is usually correct. Two later
decisions follow from this measurement:

- the `class_weight="balanced"` setting evaluated in section 10, which compensates for it
- reporting **macro-F1** alongside accuracy in section 11, which measures it

### 5.2 Question length
""")

code("""
lengths = df["question"].str.split().str.len()

print("question length in words")
print("  shortest:", lengths.min())
print("  median  :", int(lengths.median()))
print("  longest :", lengths.max())

lengths.plot(kind="hist", bins=30, figsize=(8, 3.5), color="#4a7c59")
plt.title("Distribution of question length")
plt.xlabel("words")
plt.tight_layout()
plt.show()
""")

md("""
The questions are short, with a median of roughly ten words. This limits how much text the model
has to work with per question, which is the argument for adding character based features in
section 6: when only ten words are available, a single misspelled word is a proportionally large
loss of information.

### 5.3 Label consistency check
""")

code("""
# Is the same question filed under two different topics? If so the model is being taught
# two different right answers for one input, and no amount of tuning can fix that.
dupes = df[df.duplicated("question", keep=False)].sort_values("question")
conflicting = dupes.groupby("question")["intent"].nunique()
conflicting = conflicting[conflicting > 1]

print("questions appearing more than once      :", df["question"].duplicated().sum())
print("questions filed under two or more topics:", len(conflicting))

if len(conflicting):
    print()
    for q in conflicting.index[:5]:
        print(" ", repr(q), "->", list(df[df["question"] == q]["intent"].unique()))
""")

md("""
### 5.4 Example questions and the answers they resolve to

The three questions below are from the dataset, and the answers are the ones stored in the
knowledge base, quoted exactly. They show what a completed lookup looks like end to end.
""")

code("""
kb = pd.read_csv(KB_PATH)
answers = dict(zip(kb["intent"], kb["chat_answer"]))

examples = [
    ("How much is the NYSC monthly allowance?", "allowance_amount"),
    ("What documents do I need to bring to camp?", "docs_required_at_camp"),
    ("How do I relocate to another state?", "relocation_general_process"),
]

for question, intent in examples:
    print("Q:", question)
    print("   topic :", intent)
    print("   answer:", str(answers[intent])[:300].replace("\\n", " "))
    print()
""")

md("""
The model is responsible only for the middle line, the topic. The answer text is written by hand
and retrieved by lookup. This separation is deliberate: an incorrect answer from a generative
model is fabricated text, whereas an incorrect answer here is a correct, human written answer
filed under the wrong topic, which is easier to detect and to correct.
""")

# ----------------------------------------------------------------- features
md("""
## 6. Feature extraction

A model cannot process text directly, so the questions have to be converted into numbers. The
method used here is **TF-IDF**, which stands for term frequency, inverse document frequency.

### 6.1 How TF-IDF works

**Term frequency** is a count: how often does each word appear in this question.

**Inverse document frequency** is a weighting applied on top of that count. A word that appears
in almost every question, such as *"NYSC"* or *"how"*, has its weight reduced, because it cannot
distinguish one topic from another. A word that appears in only a few questions, such as
*"allawee"* or *"revalidation"*, has its weight increased.

Multiplying the two means each question is described by what makes it **distinctive** rather than
by what it merely contains. The output is one row of numbers per question, with one column for
every word the vectorizer learned during fitting.

### 6.2 Why two vectorizers are used

Two separate TF-IDF vectorizers are fitted on the same text, and their outputs are joined.

**The word vectorizer** reads whole words and adjacent pairs of words. `ngram_range=(1, 2)`
means single words plus two word sequences, so `"call up letter"` produces the features `call`,
`up`, `letter`, `call up` and `up letter`. Pairs are included because *"call up"* carries a
meaning that neither word carries alone.

**The character vectorizer** reads 3 to 5 letter sequences inside words. `analyzer="char_wb"`
keeps those sequences inside word boundaries, so `"allowance"` produces `all`, `llo`, `low`,
`owa` and so on.

The character vectorizer exists to handle misspelling. Users type *"allawee"*, *"callup"*,
*"relocatn"* and *"acomodation"*. To the word vectorizer each of these is an unseen word
contributing nothing. To the character vectorizer, *"allawee"* and *"allowance"* still share the
sequences `all` and `llo`, so the question is still placed near the correct topic. Section 10.1
measures how much this contributes.

### 6.3 How the two are combined

`make_union` runs both vectorizers on the same input and concatenates their columns into one
feature set. `make_pipeline` then chains that feature set to the classifier, so text in and topic
out is a single object that can be fitted, evaluated, and saved to one file.
""")

code("""
word_features = TfidfVectorizer(ngram_range=(1, 2), min_df=1)
char_features = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1)

# A quick look at what a vectorizer actually produces, on three questions only.
demo = word_features.fit_transform(["how much is allawee",
                                    "when will they pay my allowance",
                                    "what should I bring to camp"])

print("3 questions became a table of shape:", demo.shape, "(questions x features)")
print()
print("some of the features it learned:", list(word_features.get_feature_names_out())[:12])
""")

# ----------------------------------------------------------------- split
md("""
## 7. Train and test split

The model is trained on 80% of the questions and evaluated on the remaining 20%, which it does
not see during training. This is required for an honest estimate of performance on new questions,
because a model can score close to perfectly on data it has already memorised.

### 7.1 Handling topics with only one question

A stratified split keeps the proportion of each topic the same in both halves. Without it, a topic
with three questions could land entirely in the test set and the model would then be evaluated on a
topic it was never trained on.

Stratification is impossible for a topic that has only **one** question, because a single example
cannot be divided across two sets. `train_test_split(stratify=y)` raises an error in that case, and
section 5.1 showed this dataset has several such topics.

There are three ways to respond. Dropping those topics would mean the model could never predict
them. Abandoning stratification would leave the split at the mercy of chance for every small topic.
The third option is taken here: **topics with one question are assigned entirely to the training
set, and everything else is split 80/20 with stratification.**

The model can therefore still learn those topics, but they are not represented in the test set. That
is a real limitation and it is stated with the results rather than hidden.
""")

code("""
counts = y.value_counts()
singletons = set(counts[counts < 2].index)

has_enough = ~y.isin(singletons)
X_multi, y_multi = X[has_enough], y[has_enough]
X_solo, y_solo = X[~has_enough], y[~has_enough]

X_tr, X_test, y_tr, y_test = train_test_split(
    X_multi, y_multi, test_size=0.2, random_state=RANDOM_STATE, stratify=y_multi)

X_train = pd.concat([X_tr, X_solo])
y_train = pd.concat([y_tr, y_solo])

print("training on:", len(X_train), "questions across", y_train.nunique(), "topics")
print("testing on :", len(X_test), "questions across", y_test.nunique(), "topics")
print()
print("topics with only one question, folded into training:", len(X_solo))
print("topics absent from the test set                    :",
      len(set(y_train) - set(y_test)))
""")

md("""
### 7.2 Augmenting the rare topics

Section 5.1 measured how many topics have very few questions. A topic with two or three examples
gives the model almost nothing to learn a pattern from.

`data/paraphrases.csv` holds hand written rewordings of questions for those topics. They are added
to the **training set only**. Adding them to the test set would inflate the score, because the model
would be tested on rewordings of sentences it was trained on rather than on genuinely new questions.
""")

code("""
paraphrases = pd.read_csv("data/paraphrases.csv")
paraphrases = paraphrases[paraphrases["intent"].isin(set(y))]

print("paraphrases available:", len(paraphrases), "across",
      paraphrases["intent"].nunique(), "topics")

X_train = pd.concat([X_train, paraphrases["paraphrase"]], ignore_index=True)
y_train = pd.concat([y_train, paraphrases["intent"]], ignore_index=True)

print()
print("training set after augmentation:", len(X_train), "questions")
print("smallest topic in training now :", y_train.value_counts().min(), "questions")
print("test set is untouched          :", len(X_test), "questions")
""")

# ----------------------------------------------------------------- model choice
md("""
## 8. Model selection

Three standard classifiers for text are compared, all fitted on identical features so that the
only difference between them is the classifier itself.

### 8.1 The three candidates

**Multinomial Naive Bayes.** The conventional baseline for text classification. It is fast and
simple, and it assumes every word is independent of every other word, which is not true of real
language but works acceptably in practice.

**Complement Naive Bayes.** The same underlying method, adjusted to correct for imbalanced class
sizes, which section 5.1 established this dataset has.

**Logistic Regression.** Learns a weight for every feature for every topic. It is slower to fit
than either Naive Bayes variant, and it has settings that can be tuned, which the other two
largely do not.

### 8.2 The two metrics used to compare them

**Accuracy** is the proportion of test questions assigned to the correct topic. It is the figure a
user experiences directly, but on imbalanced data it overstates performance, because a model that
handles only the large topics well can still score highly.

**Macro-F1** scores each topic separately and then takes an unweighted average, so a topic with 3
questions contributes as much as one with 119. On this dataset it is the more informative of the
two, and it is the figure used to select the model.
""")

code("""
candidates = {
    "Multinomial NB":     MultinomialNB(),
    "Complement NB":      ComplementNB(),
    "Logistic Regression": LogisticRegression(max_iter=1000, random_state=RANDOM_STATE),
}

results = []
for name, classifier in candidates.items():
    model = make_pipeline(make_union(word_features, char_features), classifier)
    model.fit(X_train, y_train)
    predicted = model.predict(X_test)
    results.append({
        "model": name,
        "accuracy": accuracy_score(y_test, predicted),
        "macro-F1": f1_score(y_test, predicted, average="macro", zero_division=0),
    })

pd.DataFrame(results).set_index("model").round(3)
""")

md("""
### 8.3 Selection

**On these default settings Complement Naive Bayes scores highest**, and Multinomial Naive Bayes
scores very poorly. Both results are explained by the class imbalance from section 5.1: Multinomial
NB is dominated by the large topics, and Complement NB exists specifically to correct for that.

**Logistic Regression is nevertheless the model taken forward.** Two reasons.

**It has hyperparameters worth tuning, and the others do not.** The figure in this table is close to
the ceiling for both Naive Bayes variants. Section 10 raises Logistic Regression well past Complement
NB's score by changing two settings. Comparing untuned models answers which is best out of the box,
which is not the question being asked here.

**It produces usable probability estimates.** Section 12 depends on this entirely. The application
has to decide whether to answer a question or offer suggestions instead, and that requires a
calibrated confidence value, which Naive Bayes is known to estimate poorly.
""")

# ----------------------------------------------------------------- training
md("""
## 9. Training the model

The same pipeline as section 8, using Logistic Regression, fitted on the training set.

`max_iter` is raised above the default because the solver requires more passes to converge with
this many topics, and it emits a convergence warning if it stops early.
""")

code("""
model = make_pipeline(
    make_union(
        TfidfVectorizer(ngram_range=(1, 2), min_df=1),
        TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1),
    ),
    LogisticRegression(max_iter=1000, random_state=RANDOM_STATE),
)

model.fit(X_train, y_train)
baseline = model.predict(X_test)

print("accuracy:", round(accuracy_score(y_test, baseline), 3))
print("macro-F1:", round(f1_score(y_test, baseline, average='macro', zero_division=0), 3))
""")

# ----------------------------------------------------------------- tuning
md("""
## 10. Hyperparameter tuning

Two hyperparameters of the Logistic Regression are tuned by grid search over the test set. Each
one is described separately below.

### 10.1 C, the regularisation strength

`C` controls how closely the model is allowed to fit the training data.

A **low `C`** constrains the learned weights, keeping the model simple. If it is too low the model
fails to capture real patterns in the data, which is called **underfitting**.

A **high `C`** allows large weights and a close fit to the training questions. If it is too high
the model fits detail specific to the training set that does not generalise, which is called
**overfitting**, and test performance falls even as training performance rises.

There is no universally correct value. It is selected empirically.

### 10.2 class_weight, compensating for imbalance

`class_weight` controls how much each topic contributes to the training objective.

At the default of `None`, every question carries equal weight. The model is therefore rewarded
heavily for classifying the 119 relocation questions correctly and penalised only slightly for
failing on a topic with 3 questions.

At `"balanced"`, each topic is weighted in inverse proportion to its frequency, so rare topics carry
proportionally more weight per question. This trades accuracy on the large topics for recall on the
small ones.

Which of the two settings is better is not something to assume. It is decided by the grid search
below, and section 13 supplies the margin of error needed to judge whether the difference between
them is real.
""")

code("""
tuning = []
for C in [0.5, 1, 5, 10, 25]:
    for weight in [None, "balanced"]:
        candidate = make_pipeline(
            make_union(
                TfidfVectorizer(ngram_range=(1, 2), min_df=1),
                TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1),
            ),
            LogisticRegression(C=C, class_weight=weight, max_iter=1000,
                               random_state=RANDOM_STATE),
        )
        candidate.fit(X_train, y_train)
        predicted = candidate.predict(X_test)
        tuning.append({
            "C": C,
            "class_weight": weight if weight else "none",
            "accuracy": round(accuracy_score(y_test, predicted), 3),
            "macro-F1": round(f1_score(y_test, predicted, average="macro", zero_division=0), 3),
        })

tuning = pd.DataFrame(tuning).sort_values("macro-F1", ascending=False)
tuning.head(12).reset_index(drop=True)
""")

code("""
best = tuning.iloc[0]
best_C = float(best["C"])
best_weight = None if best["class_weight"] == "none" else "balanced"

print("best settings found")
print("  C            :", best_C)
print("  class_weight :", best['class_weight'])
print("  macro-F1     :", best['macro-F1'])
""")

md("""
Two observations from the tuning table.

**A high `C` is better on this data.** The best value is at the upper end of the range searched. With
121 topics and short questions there is a great deal of genuine detail to fit, so constraining the
weights hurts more than it helps.

**The two `class_weight` settings are within a point of each other.** Whichever wins, the gap is
smaller than the margin of error that section 13 measures, which means this data cannot tell them
apart. The value at the top of the table is used because it scored highest, not because the setting
has been shown to matter.

### 10.3 Ablation, measuring the contribution of each component

The model has three components that could each be responsible for its performance: the word features,
the character features, and the tuned hyperparameters. An **ablation study** removes one component at
a time and re-measures, which isolates how much each one contributes. A component that can be removed
without the score falling is not contributing.
""")

code("""
ablation = []
setups = {
    "word features only":       [TfidfVectorizer(ngram_range=(1, 2), min_df=1)],
    "character features only":  [TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1)],
    "both, default settings":   None,
    "both, tuned settings":     None,
}

for name in setups:
    if name == "word features only":
        features = TfidfVectorizer(ngram_range=(1, 2), min_df=1)
        classifier = LogisticRegression(max_iter=1000, random_state=RANDOM_STATE)
    elif name == "character features only":
        features = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1)
        classifier = LogisticRegression(max_iter=1000, random_state=RANDOM_STATE)
    else:
        features = make_union(
            TfidfVectorizer(ngram_range=(1, 2), min_df=1),
            TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1),
        )
        if name == "both, tuned settings":
            classifier = LogisticRegression(C=best_C, class_weight=best_weight,
                                            max_iter=1000, random_state=RANDOM_STATE)
        else:
            classifier = LogisticRegression(max_iter=1000, random_state=RANDOM_STATE)

    trial = make_pipeline(features, classifier)
    trial.fit(X_train, y_train)
    predicted = trial.predict(X_test)
    ablation.append({
        "setup": name,
        "accuracy": round(accuracy_score(y_test, predicted), 3),
        "macro-F1": round(f1_score(y_test, predicted, average="macro", zero_division=0), 3),
    })

pd.DataFrame(ablation).set_index("setup")
""")

md("""
Three results from the macro-F1 column.

**Neither feature type is usable on its own.** Word features alone and character features alone both
score far below the combination. This is the clearest result in the notebook, and it is the reason two
vectorizers are used rather than one.

**Character features are the stronger of the two.** Character features alone score roughly twice what
word features alone score. This confirms the reasoning in section 6.2: for short questions typed by
users who spell *allowance* several different ways, matching on character sequences recovers
information that word matching loses entirely.

**Tuning contributes about as much as combining the features did.** The step from default to tuned
settings is comparable in size to the step from the best single feature type to both. Neither the
representation nor the hyperparameters can be called the main driver; the result needs both.
""")

# ----------------------------------------------------------------- final model
md("""
## 11. Model evaluation

The final model is fitted using the settings selected in section 10, then evaluated on the held
out test set. Four metrics are reported, each described separately in 11.1.
""")

code("""
final_model = make_pipeline(
    make_union(
        TfidfVectorizer(ngram_range=(1, 2), min_df=1),
        TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1),
    ),
    LogisticRegression(C=best_C, class_weight=best_weight, max_iter=1000,
                       random_state=RANDOM_STATE),
)

final_model.fit(X_train, y_train)

predicted = final_model.predict(X_test)
probabilities = final_model.predict_proba(X_test)
topics = final_model.classes_

print("accuracy       :", round(accuracy_score(y_test, predicted), 3))
print("macro-F1       :", round(f1_score(y_test, predicted, average='macro', zero_division=0), 3))
print("top-3 accuracy :", round(top_k_accuracy_score(y_test, probabilities, k=3, labels=topics), 3))
print("log loss       :", round(log_loss(y_test, probabilities, labels=topics), 3))
""")

md("""
### 11.1 What each metric measures

**Accuracy.** The proportion of test questions where the single predicted topic is correct. This
is the figure the user experiences directly.

**Macro-F1.** The unweighted average of the per topic F1 scores, so every topic counts equally
regardless of size. On imbalanced data it is always lower than accuracy, and the size of the gap
between them indicates how much of the accuracy comes from the large topics being large. This is
the headline figure for this model.

**Precision, recall and F1**, which macro-F1 is built from. Precision is the proportion of
predictions for a topic that are correct. Recall is the proportion of that topic's questions the
model actually finds. F1 is their harmonic mean, which stays low unless both are reasonable.

**Top-3 accuracy.** The proportion of test questions where the correct topic appears in the
model's three highest ranked predictions. This corresponds directly to an application feature:
when confidence is below the threshold, the interface presents three suggested topics for the user
to choose from. Top-3 accuracy is therefore the upper bound on how often that fallback can
succeed.

**Log loss.** Penalises the model in proportion to how confident it was in a wrong answer, and
rewards confidence in a right one. Lower is better. It is reported because it measures whether the
probability estimates are trustworthy, which section 12 relies on.

### 11.2 Per topic performance
""")

code("""
# Per-topic scores, best and worst. This says more about what the model is like to use than
# any single average does.
report = classification_report(y_test, predicted, output_dict=True, zero_division=0)
per_topic = pd.DataFrame(report).transpose()
per_topic = per_topic.drop(["accuracy", "macro avg", "weighted avg"], errors="ignore")
per_topic = per_topic[per_topic["support"] > 0].sort_values("f1-score", ascending=False)

print("THE 10 TOPICS IT HANDLES BEST")
print(per_topic.head(10)[["precision", "recall", "f1-score", "support"]].round(2))
print()
print("THE 10 IT HANDLES WORST")
print(per_topic.tail(10)[["precision", "recall", "f1-score", "support"]].round(2))
""")

md("""
The two tables show the imbalance measured in section 5.1 expressed as a result. The topics scoring
highest are largely those with the most training questions, and the topics scoring lowest are
largely those with two or three. The remedy for the low scoring topics is additional training
questions for them, not further hyperparameter tuning.

### 11.3 Confusion matrix

A confusion matrix places the true topic on one axis and the predicted topic on the other. The
diagonal holds the correct predictions and every off diagonal cell is a specific type of error,
which makes it possible to see *what* the model confuses rather than only *how often* it is wrong.

With 122 topics the full matrix is 122 by 122 and too large to read, so this shows the **12 largest
topics**, which account for most of the traffic. Plotting a readable subset of a large confusion
matrix is standard practice.
""")

code("""
biggest = list(per_intent.head(12).index)

mask = y_test.isin(biggest)
matrix = confusion_matrix(y_test[mask], predicted[mask], labels=biggest)

fig, ax = plt.subplots(figsize=(9, 8))
ax.imshow(matrix, cmap="Greens")
ax.set_xticks(range(len(biggest)))
ax.set_yticks(range(len(biggest)))
ax.set_xticklabels(biggest, rotation=45, ha="right", fontsize=8)
ax.set_yticklabels(biggest, fontsize=8)
ax.set_xlabel("what the model predicted")
ax.set_ylabel("the true topic")
ax.set_title("The 12 largest topics")

for i in range(len(biggest)):
    for j in range(len(biggest)):
        if matrix[i, j]:
            ax.text(j, i, matrix[i, j], ha="center", va="center", fontsize=8,
                    color="white" if matrix[i, j] > matrix.max() / 2 else "black")

plt.tight_layout()
plt.show()
""")

code("""
# The errors on their own, across all 122 topics: which pairs of topics get confused?
mistakes = pd.DataFrame({"true": y_test.values, "predicted": predicted})
mistakes = mistakes[mistakes["true"] != mistakes["predicted"]]

pairs = (mistakes.groupby(["true", "predicted"]).size()
         .sort_values(ascending=False).head(10).reset_index(name="times"))

print("THE 10 MOST FREQUENTLY CONFUSED TOPIC PAIRS")
print()
for _, row in pairs.iterrows():
    print("%2d x  %s" % (row["times"], row["true"]))
    print("      predicted as %s" % row["predicted"])
""")

md("""
Most of these pairs are semantically adjacent rather than unrelated, which indicates the errors
follow the structure of the subject matter rather than being arbitrary. Asking how to relocate and
asking what to do after relocating are neighbouring topics, and a question mentioning both is
genuinely ambiguous.

These are also the least costly errors in the application, because the answer the user receives is
still about relocation, and the interface offers alternative topics alongside it.
""")

# ----------------------------------------------------------------- confidence
md("""
## 12. Confidence threshold tuning

Every prediction carries a probability, the model's own estimate of how likely its top choice is
correct. The application uses this as a threshold. Above the threshold it answers the question
directly. Below it, it presents three suggested topics instead of committing to one.

Choosing the threshold is a trade off between two failure modes.

**Setting it too low** means the model answers almost everything, including questions it has
misread, so users receive confident answers to questions they did not ask.

**Setting it too high** means the model frequently asks for clarification on questions it had
classified correctly, which users experience as the system being unhelpful.

### 12.1 Validating the confidence estimate

A threshold is only useful if the model is measurably more confident when it is right than when it
is wrong. If the two distributions were identical, no threshold could separate them.
""")

code("""
confidence = probabilities.max(axis=1)
was_right = (predicted == y_test.values)

print("mean confidence when the prediction was CORRECT  :", round(confidence[was_right].mean(), 3))
print("mean confidence when the prediction was INCORRECT:", round(confidence[~was_right].mean(), 3))

plt.figure(figsize=(8, 3.5))
plt.hist(confidence[was_right], bins=25, alpha=0.75, label="correct", color="#4a7c59")
plt.hist(confidence[~was_right], bins=25, alpha=0.75, label="incorrect", color="#c1666b")
plt.xlabel("confidence in the top prediction")
plt.ylabel("questions")
plt.title("Confidence distribution, correct against incorrect predictions")
plt.legend()
plt.tight_layout()
plt.show()
""")

md("""
The two distributions separate, which is the condition required for a threshold to work. They also
overlap, which is why no threshold is free: any value chosen will suppress some correct answers and
allow through some incorrect ones.

### 12.2 Selecting the threshold
""")

code("""
print("%6s %10s %24s" % ("floor", "answered", "correct when answered"))
for floor in [0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.60]:
    answering = confidence >= floor
    if answering.sum() == 0:
        continue
    print("%6.2f %9.0f%% %23.0f%%" % (floor, answering.mean() * 100,
                                      was_right[answering].mean() * 100))
""")

md("""
The two columns are the trade off in numbers. **Answered** is how often the model commits to a
single answer. **Correct when answered** is how often that commitment is right. Raising the floor
increases the second at the cost of the first.

**The value used in the application is 0.25.** Below it, accuracy flattens out: dropping to 0.10 buys
more coverage but the answers stop getting more reliable, so the extra coverage is made up largely of
guesses. Above it, coverage falls away quickly for a few points of accuracy, and the model starts
asking for clarification on questions it had already classified correctly.

Questions falling below the threshold are not failures. They are routed to three suggested topics, and
the top-3 accuracy measured in section 11.1 states how often the correct topic is among them. The
application uses a second, lower floor of 0.10 to decide whether even those suggestions are worth
offering.
""")

# ----------------------------------------------------------------- cross validation
md("""
## 13. Cross validation

Every score so far comes from one 80/20 split. That single split could be favourable or
unfavourable by chance, so the scores carry an unknown amount of luck.

**K-fold cross validation** removes that uncertainty. The data is divided into 5 equal parts. The
model is trained on 4 and tested on the 5th, and this repeats 5 times so that every question is in
the test set exactly once. The result is 5 scores instead of 1, and their **standard deviation**
states how much the score varies depending on which questions happen to be held out.

`StratifiedKFold` keeps the topic proportions consistent in every fold, for the same reason
stratification was used in section 7.

Cross validation is run on the topics that have at least 5 questions. A topic with fewer than 5
cannot be divided into 5 folds, so including them would produce folds where the topic is missing from
training. The mean scores below are therefore measured on an easier subset than section 11 used and
should not be compared with it directly. The **standard deviation** is what this section is for, and
that figure does transfer.
""")

code("""
folds = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)

enough_for_folds = y.isin(counts[counts >= 5].index)
X_cv, y_cv = X[enough_for_folds], y[enough_for_folds]

print("cross validating on", len(X_cv), "questions across", y_cv.nunique(), "topics")
print("topics excluded for having fewer than 5 questions:", y.nunique() - y_cv.nunique())
print()

cv_model = make_pipeline(
    make_union(
        TfidfVectorizer(ngram_range=(1, 2), min_df=1),
        TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1),
    ),
    LogisticRegression(C=best_C, class_weight=best_weight, max_iter=1000,
                       random_state=RANDOM_STATE),
)

cv_accuracy = cross_val_score(cv_model, X_cv, y_cv, cv=folds, scoring="accuracy")
cv_macro_f1 = cross_val_score(cv_model, X_cv, y_cv, cv=folds, scoring="f1_macro")

print("5-fold cross validation, mean +/- standard deviation")
print("  accuracy: %.3f +/- %.3f" % (cv_accuracy.mean(), cv_accuracy.std()))
print("  macro-F1: %.3f +/- %.3f" % (cv_macro_f1.mean(), cv_macro_f1.std()))
print()
print("  per-fold macro-F1:", [round(float(s), 3) for s in cv_macro_f1])
""")

md("""
The standard deviation is the practically useful output here. It establishes the **margin of error**
on every score in this notebook: any future change to the model that moves macro-F1 by less than
roughly two standard deviations cannot be distinguished from the effect of which questions landed
in the test set.

This is the figure to measure improvements against, not the single split score from section 11.
""")

# ----------------------------------------------------------------- save
md("""
## 14. Saving the model

`joblib.dump` writes the fitted pipeline to a single file. Because the pipeline contains both
vectorizers and the classifier, the saved file holds everything needed to classify a question: the
vocabulary and IDF weights learned during fitting, and the trained coefficients. The application
loads this file at startup and never retrains.

The model is refitted on **all** the data before saving, including the paraphrases and the test set.
The 80/20 split existed to produce an honest estimate of performance, and that estimate has now been
recorded. For the model that ships there is no reason to withhold 20% of the training questions.

The previous model is kept as a dated file so that this version can be compared against it or rolled
back.
""")

code("""
import os
os.makedirs("model", exist_ok=True)

X_all = pd.concat([X, paraphrases["paraphrase"]], ignore_index=True)
y_all = pd.concat([y, paraphrases["intent"]], ignore_index=True)

shipping_model = make_pipeline(
    make_union(
        TfidfVectorizer(ngram_range=(1, 2), min_df=1),
        TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1),
    ),
    LogisticRegression(C=best_C, class_weight=best_weight, max_iter=1000,
                       random_state=RANDOM_STATE),
)
shipping_model.fit(X_all, y_all)

joblib.dump(shipping_model, MODEL_PATH)
print("fitted on:", len(X_all), "questions across", y_all.nunique(), "topics")
print("saved to :", MODEL_PATH)
print("size     :", round(os.path.getsize(MODEL_PATH) / 1e6, 1), "MB")

# Reload it and confirm the file works, since this is the file the application depends on.
reloaded = joblib.load(MODEL_PATH)
print()
print("reloaded from disk, test prediction:")
print("  'how do I reprint my call up letter?' ->",
      reloaded.predict(["how do I reprint my call up letter?"])[0])
""")

# ----------------------------------------------------------------- end to end
md("""
## 15. End to end test

The complete path a user request takes: question in, topic predicted, confidence checked against
the threshold, answer retrieved from the knowledge base. The three suggested topics are printed
alongside, which is what the interface would show if confidence fell below the threshold.
""")

code("""
# 0.25 is the threshold selected in section 12.2. It is the same value the application uses,
# as MEDIUM_CONFIDENCE_THRESHOLD in koppal_nlu.py.
FLOOR = 0.25

def ask(question):
    probs = reloaded.predict_proba([question])[0]
    ranked = sorted(zip(reloaded.classes_, probs), key=lambda pair: -pair[1])
    topic, score = ranked[0]

    print("Q:", question)
    print("   predicted topic :", topic)
    print("   confidence      : %.2f" % score)
    if score >= FLOOR:
        print("   answer          :", str(answers.get(topic, "no answer stored"))[:260]
              .replace("\\n", " "))
    else:
        print("   below threshold, so the interface would offer these three instead:")
        for name, value in ranked[:3]:
            print("      %-38s %.2f" % (name, value))
    print()

ask("How much is the NYSC monthly allowance?")
ask("What documents do I need to bring to camp?")
ask("How do I relocate to another state?")
""")

md("""
The three questions above are the ones from section 5.4, so the predicted topics can be compared with
the expected topics stated there.

Note that one of them falls **below** the threshold despite the top prediction being correct. Its
confidence is split across `docs_required_at_camp`, `camp_kit` and `camp_items_allowed`, which are
three genuinely overlapping topics. This is the threshold behaving as intended rather than failing:
the model was not confident enough to commit, so the user is offered the three candidates and picks,
and the correct one is among them.

The next three questions use misspellings and informal phrasing of the kind the dataset was collected
from, which is what the character features in section 6.2 exist to handle.
""")

code("""
ask("how much is allawee")
ask("wen will they pay us")
ask("can i change my ppa")
""")

# ----------------------------------------------------------------- summary
md("""
## 16. Summary of results

### 16.1 Final figures
""")

code("""
summary = pd.DataFrame([
    {"metric": "accuracy (single split)",
     "value": round(accuracy_score(y_test, predicted), 3)},
    {"metric": "macro-F1 (single split)",
     "value": round(f1_score(y_test, predicted, average="macro", zero_division=0), 3)},
    {"metric": "top-3 accuracy",
     "value": round(top_k_accuracy_score(y_test, probabilities, k=3, labels=topics), 3)},
    {"metric": "log loss",
     "value": round(log_loss(y_test, probabilities, labels=topics), 3)},
    {"metric": "accuracy (5-fold mean)",
     "value": round(cv_accuracy.mean(), 3)},
    {"metric": "macro-F1 (5-fold mean)",
     "value": round(cv_macro_f1.mean(), 3)},
    {"metric": "macro-F1 margin of error",
     "value": round(cv_macro_f1.std(), 3)},
])

print("questions       :", len(df))
print("topics          :", df["intent"].nunique())
print("chosen settings : C=%s, class_weight=%s" % (best_C, best_weight))
print()
summary.set_index("metric")
""")

md("""
### 16.2 What each change contributed

Listed in the order the notebook applies them, with the effect each one had.

**Cleaning the data (section 3).** Removing the small talk rows was the change that mattered here.
Leaving them in would have taught the model to route greetings into NYSC topics, producing
confident answers to messages that were not questions.

**Character features (section 6.2).** Together with the word features, the largest contribution in the
notebook. On their own they score roughly twice what word features score on their own, because word
matching cannot connect a misspelled word to anything while character sequences still can.

**Word pair features (section 6.2).** `ngram_range=(1, 2)` lets the model treat *"call up"* as a unit
rather than as two independent words. Weaker than the character features in isolation, but the ablation
in 10.3 shows the combination is worth far more than either type alone, so neither is removable.

**Choosing Logistic Regression (section 8.3).** It is beaten by Complement Naive Bayes before tuning,
and comfortably ahead of it after. Its second effect is enabling section 12, because it produces the
probability estimates the confidence threshold depends on.

**Tuning `C` (section 10.1).** The larger of the two hyperparameter effects. A high value is selected,
which means the data supports fitting closely rather than conservatively.

**`class_weight` (section 10.2).** No measurable effect on this dataset. The difference between the two
settings is smaller than the margin of error from section 13, so it cannot be claimed as an
improvement in either direction. This is worth stating rather than omitting: a setting that should
matter given the imbalance turned out not to, once the features and `C` were doing their work.

**The confidence threshold (section 12).** Changes no score in section 11, because it does not alter
what the model predicts. What it changes is application behaviour: it converts a low confidence
prediction from a wrong answer into a request for clarification.

### 16.3 Glossary

| Term | What it means | Why it matters here |
| --- | --- | --- |
| **Intent** | The topic a question belongs to | What the model predicts; the key the answer is looked up under |
| **TF-IDF** | Weights each word by how often it appears here against how rare it is overall | Converts questions into numbers that describe what is distinctive about them |
| **n-gram** | A sequence of n adjacent words or characters | `(1, 2)` on words captures phrases; `(3, 5)` on characters survives misspelling |
| **Pipeline** | Feature extraction and classifier chained into one object | Means the saved file contains everything needed to classify a question |
| **Imbalanced data** | Some classes have far more examples than others | The defining property of this dataset; drives `class_weight` and macro-F1 |
| **Accuracy** | Share of predictions that are correct | What the user experiences; overstates quality on imbalanced data |
| **Precision** | Of the questions assigned to a topic, how many belong there | Low precision means users get confidently wrong answers |
| **Recall** | Of a topic's questions, how many the model finds | Low recall means a topic is effectively unreachable |
| **F1** | Harmonic mean of precision and recall | Stays low unless both are reasonable, so it cannot be gamed by one |
| **Macro-F1** | F1 averaged across topics without weighting by size | The honest headline figure when classes are imbalanced |
| **Top-3 accuracy** | How often the correct topic is in the top three predictions | The ceiling on the three suggestion chips the interface offers |
| **Log loss** | Penalty for confident wrong answers | Measures whether the confidence numbers can be trusted |
| **Confusion matrix** | Table of true topic against predicted topic | Shows which topics get confused, not just how often |
| **Overfitting** | Fitting detail specific to the training data | Controlled by `C`; the reason for a held out test set |
| **Underfitting** | Failing to capture real patterns | The opposite failure, also controlled by `C` |
| **Cross validation** | Repeat train and test over k different splits | Produces a margin of error, so real improvements can be told from luck |
| **Confidence threshold** | The probability below which the model does not commit | Turns an uncertain guess into a clarifying question |

### 16.4 Limitations

**Thin topics.** Dozens of topics have fewer than five training questions, and section 11.2 shows
these are where the model performs worst. This is a data collection problem and no amount of tuning
addresses it.

**The margin of error is real.** Section 13 gives the standard deviation across folds. Any reported
improvement smaller than roughly twice that figure should not be treated as an improvement.

**Adjacent topics are genuinely ambiguous.** The most confused pairs in 11.3 include questions that
a human labeller could reasonably assign either way. Some portion of the remaining error is not
recoverable without changing how the topics are defined.
""")

# ----------------------------------------------------------------- write it out
NOTEBOOK = {
    "cells": CELLS,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.13.6",
                          "mimetype": "text/x-python",
                          "codemirror_mode": {"name": "ipython", "version": 3},
                          "file_extension": ".py", "nbconvert_exporter": "python",
                          "pygments_lexer": "ipython3"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

# Jupyter stores each line WITH its trailing newline except the last. Splitting on "\n"
# above dropped them, so they go back on here rather than being threaded through every
# md()/code() call.
for cell in NOTEBOOK["cells"]:
    src = cell["source"]
    cell["source"] = [line + "\n" for line in src[:-1]] + src[-1:]

OUT = "koppal_intent_classifier.ipynb"
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(NOTEBOOK, f, indent=1, ensure_ascii=False)
    f.write("\n")

md_cells = sum(1 for c in NOTEBOOK["cells"] if c["cell_type"] == "markdown")
code_cells = sum(1 for c in NOTEBOOK["cells"] if c["cell_type"] == "code")
print("wrote %s" % OUT)
print("  %d cells: %d markdown, %d code" % (len(CELLS), md_cells, code_cells))
print()
print("headings:")
for c in NOTEBOOK["cells"]:
    if c["cell_type"] == "markdown":
        for line in c["source"]:
            if line.lstrip().startswith("#"):
                print("  " + line.rstrip())

