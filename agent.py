"""The Agent That Grows Up: a campus helper that starts with a wrong belief,
gets corrected, and shows the literal diff between its old and new rule.

Rules live in a MeTTa-style text file (kb.metta). Every change is written to
an append-only audit trail (audit.jsonl), so the agent's growth is inspectable
and survives restarts (persistence across sessions).
"""
import difflib
import json
import re
import shutil
import time
from pathlib import Path

HERE = Path(__file__).parent
KB = HERE / "kb.metta"
AUDIT = HERE / "audit.jsonl"
SEED = HERE / "seed_rules.metta"

# Words too generic to serve as a *required* match on their own when a new
# topic is auto-registered (see learn() below) — without this, two unrelated
# new topics that both happen to contain "time" (e.g. "gym-opening-time" and
# "lunch-time") would falsely match each other's questions.
_GENERIC_TOPIC_WORDS = {
    "time", "hours", "hour", "day", "date", "deadline", "location",
    "place", "name", "number", "info", "details", "schedule",
}

# Each topic needs at least one "key" word hit to qualify. "bonus" words don't
# qualify a topic on their own (they're too generic / shared across topics)
# but they add to the score so paraphrased questions still match correctly.
TOPIC_WORDS = {
    "library-closing-time": {
        "key": {"library", "closing", "closes"},
        "bonus": {"hours", "time", "open"}},
    "canteen-location": {
        "key": {"canteen", "cafeteria", "mess"},
        "bonus": {"food", "eat", "location", "where"}},
    "wifi-password": {
        "key": {"wifi", "wi-fi", "internet", "network"},
        "bonus": {"password", "connect"}},
    "helpdesk-hours": {
        "key": {"helpdesk", "support"},
        "bonus": {"help", "desk", "hours", "time"}},
    "registration-deadline": {
        "key": {"registration", "register", "signup", "deadline"},
        "bonus": {"when", "due"}},
    "bus-route": {
        "key": {"bus", "shuttle", "transport"},
        "bonus": {"route", "schedule", "time"}},
}
ANSWER_RE = r'^\(= \(answer {t}\) "(.*)"\)$'


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


class Agent:
    def __init__(self, kb=KB, audit=AUDIT, seed=SEED):
        self.kb, self.audit = Path(kb), Path(audit)
        if not self.kb.exists():
            shutil.copy(seed, self.kb)   # first run: start from seed beliefs
        self.last_topic = None

    # ---- reading beliefs -------------------------------------------------
    def text(self):
        return self.kb.read_text()

    def belief(self, topic):
        m = re.search(ANSWER_RE.format(t=re.escape(topic)), self.text(), re.M)
        return m.group(1) if m else None

    def confidence(self, topic):
        m = re.search(rf"^\(= \(confidence {re.escape(topic)}\) ([0-9.]+)\)$",
                      self.text(), re.M)
        return float(m.group(1)) if m else None

    def find_topic(self, question):
        words = set(re.findall(r"[a-z]+", question.lower()))
        best_topic, best_score = None, 0
        for topic, groups in TOPIC_WORDS.items():
            key_hits = len(words & groups["key"])
            if key_hits == 0:
                continue                         # must match a specific word
            score = key_hits + len(words & groups.get("bonus", set()))
            if score > best_score:
                best_topic, best_score = topic, score
        return best_topic

    # ---- answering (with a visible reasoning trail) ------------------------
    def ask(self, question):
        topic = self.find_topic(question)
        self.last_topic = topic
        if topic is None or self.belief(topic) is None:
            return {"answer": None, "topic": topic, "trail": [
                "I searched my rules for this topic and found none.",
                "I am uncertain, so I will ask you instead of guessing."]}
        val, conf = self.belief(topic), self.confidence(topic)
        return {"answer": val, "topic": topic, "trail": [
            f"Matched question to topic '{topic}'.",
            f"Rule found: (= (answer {topic}) \"{val}\").",
            f"My confidence in this rule is {conf}."]}

    # ---- learning ----------------------------------------------------------
    def learn(self, topic, new_value, reason="user correction"):
        """Create or replace a rule. Returns (diff_text, audit_record)."""
        topic, new_value = slug(topic), new_value.strip().replace('"', "'")
        if not topic or not new_value:
            raise ValueError("topic and value must be non-empty")
        old_text = self.text()
        old_val = self.belief(topic)
        if old_val == new_value:
            return "", None                      # nothing to learn
        answer = f'(= (answer {topic}) "{new_value}")'
        conf = f"(= (confidence {topic}) 0.9)"
        if old_val is None:                      # new knowledge: append
            new_text = old_text.rstrip("\n") + f"\n{answer}\n{conf}\n"
        else:                                    # correction: rewrite in place
            new_text = re.sub(ANSWER_RE.format(t=re.escape(topic)), answer,
                              old_text, flags=re.M)
            new_text = re.sub(rf"^\(= \(confidence {re.escape(topic)}\) [0-9.]+\)$",
                              conf, new_text, flags=re.M)
        self.kb.write_text(new_text)
        diff = "".join(difflib.unified_diff(
            old_text.splitlines(True), new_text.splitlines(True),
            "rules (before)", "rules (after)"))
        record = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "topic": topic,
                  "old": old_val, "new": new_value, "reason": reason,
                  "diff": diff}
        with self.audit.open("a") as f:
            f.write(json.dumps(record) + "\n")
        if topic not in TOPIC_WORDS:             # make new topics findable
            parts = set(topic.split("-"))
            key_parts = parts - _GENERIC_TOPIC_WORDS
            if not key_parts:                    # topic is all-generic words
                key_parts = parts                # (rare) — keep it findable at all
            TOPIC_WORDS[topic] = {"key": key_parts, "bonus": parts - key_parts}
        return diff, record

    def history(self):
        if not self.audit.exists():
            return []
        return [json.loads(l) for l in self.audit.read_text().splitlines()]


def chat(agent):
    """Interactive CLI. Fully local — no external API, no API key, no
    network calls. local_nlp.py recognizes free-form corrections
    ("no, ...", "actually ...") and chit-chat with regex, and varies the
    wording of replies with templates. Every fact and every rule diff
    still comes straight from the Agent above, unedited.
    """
    import local_nlp as nlp
    print("SJIT Campus Helper (fully local — no API key needed).")
    print("Ask a question, correct me ('no, ...' / 'actually ...'), or say hi.")
    print("Commands: /rules  /history  /trail  /quit\n")
    pending = None                                # topic awaiting a taught answer
    last_trail = []
    while True:
        try:
            line = input("you> ").strip()
        except EOFError:
            break
        if not line:
            continue
        if line == "/quit":
            break
        if line == "/rules":
            print(agent.text()); continue
        if line == "/history":
            for h in agent.history():
                print(f"[{h['time']}] {h['topic']}: {h['old']!r} -> {h['new']!r}")
            continue
        if line == "/trail":
            for step in last_trail:
                print("  [why]", step)
            continue

        if nlp.is_chit_chat(line):
            print("agent>", nlp.phrase_chat(line))
            continue

        if pending:                               # answering my clarifying question
            diff, _ = agent.learn(pending, line, "answer to clarifying question")
            print("agent>", nlp.phrase_learned(line))
            print("  [rule diff]\n" + diff)
            pending = None
            continue

        correction = nlp.try_correction(line)
        if correction:
            target = agent.find_topic(line) or agent.last_topic
            if target:
                diff, _ = agent.learn(target, correction, "user correction")
                print("agent>", nlp.phrase_corrected(correction))
                print("  [rule diff]\n" + diff)
                continue

        subject, value = nlp.try_statement(line)
        if subject and value:
            new_topic = nlp.topic_slug_from_text(subject)
            if agent.belief(new_topic) is None:   # only auto-add genuinely new facts
                diff, _ = agent.learn(new_topic, value, "auto-added new fact")
                print("agent>", nlp.phrase_learned(value))
                print("  [rule diff]\n" + diff)
                continue
            # topic already known -> fall through and treat this as a
            # question instead of silently overwriting existing data

        r = agent.ask(line)
        last_trail = r["trail"]
        if r["answer"]:
            print("agent>", nlp.phrase_answer(r["answer"]))
        else:
            pending = nlp.topic_slug_from_text(line) if r["topic"] is None else r["topic"]
            print("agent>", nlp.phrase_unknown())
        print("  (type /trail to see exactly which rule I used and why)")


if __name__ == "__main__":
    chat(Agent())
