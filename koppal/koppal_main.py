"""
main.py -- entry point. Loads the model and KB once, then runs the
message loop: user input -> dialogue_manager.handle_message() -> reply.
No NYSC content, no decision logic, no lookup data here -- just wiring.
"""

import csv
import sys

import koppal_nlu as nlu
import koppal_dialogue_manager as dialogue_manager

KB_PATH = "data/koppal_knowledge_base.csv"

# Expected columns in knowledge_base.csv (intent_summary_corrected.csv),
# per chatbot_architecture_v2.md Section 1:
#   intent, answer_type, answer, follow_up_trigger, follow_up_answer
_kb = {}


def load_kb(path: str = KB_PATH):
    """Load the KB CSV into a dict keyed by intent. Call once at startup."""
    global _kb
    _kb = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            _kb[row["intent"]] = row
    return _kb


def kb_lookup(intent: str):
    """kb_lookup_fn passed to dialogue_manager -- returns the KB row dict for
    an intent, or None if the intent isn't in the KB (e.g. chitchat intents,
    which live in chitchat.py, not the CSV)."""
    return _kb.get(intent)


def classify(message: str):
    """classify_fn passed to dialogue_manager -- thin pass-through to nlu.py."""
    return nlu.classify(message)


def run():
    nlu.load_model()
    load_kb()
    state = dialogue_manager.ConversationState()

    print("NYSC FAQ Bot -- type 'quit' to exit.")
    while True:
        try:
            message = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBot: Bye for now!")
            break

        if message.lower() in ("quit", "exit"):
            print("Bot: Bye for now!")
            break
        if not message:
            continue

        reply = dialogue_manager.handle_message(message, state, classify, kb_lookup)
        print(f"Bot: {reply}")


if __name__ == "__main__":
    run()
