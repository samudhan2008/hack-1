"""Local natural-language helpers — no external AI API, no network calls.

Two jobs, both done with plain regex and template pools:
  1. Recognize when free text is a correction ("no, ...", "actually ...",
     "that's wrong, ...") or small talk (greetings/thanks), so the CLI and
     the API don't need the rigid "no, <answer>" syntax.
  2. Vary the wording of replies so the same fact doesn't always come back
     as the exact same sentence. This is templated, not generated — the
     agent's actual facts, rule diffs, and audit trail are untouched and
     come only from agent.py.
"""
import random
import re

_CORRECTION_RE = re.compile(
    r"^(?:no|nope|nah|wrong|incorrect|not (?:right|correct)|"
    r"that'?s (?:not right|wrong|incorrect)|actually|"
    r"it'?s actually|it is actually|correction)\b[,:]?\s*(.+)$", re.I)

_GREETING_RE = re.compile(
    r"^(?:hi|hello|hey|yo|good (?:morning|afternoon|evening))\b", re.I)
_THANKS_RE = re.compile(r"^(?:thanks|thank you|thx|ty|cheers)\b", re.I)
_BYE_RE = re.compile(r"^(?:bye|goodbye|see ya|later)\b", re.I)


_LEADING_CLAUSE_RE = re.compile(
    r"^(?:the\s+)?[a-z0-9 \-']+?\s+(?:is|are|was|were)\s+(.+)$", re.I)

# A one-shot declarative statement: "<subject> is/are/was/were <value>".
# Deliberately requires no leading question word and no '?' — see
# try_statement() below for why.
_STATEMENT_RE = re.compile(
    r"^(?:the\s+)?([a-z][a-z0-9 \-']*?)\s+(?:is|are|was|were)\s+(.+)$", re.I)

# Words to strip out when turning a question into a topic slug, so
# "when is the lunch time" -> "lunch-time" instead of
# "when-is-the-lunch-time".
_STOPWORDS = {
    "what", "whats", "when", "where", "how", "who", "which", "why",
    "is", "are", "was", "were", "does", "do", "did", "can", "could",
    "would", "should", "will", "the", "a", "an", "of", "for", "on", "at",
    "in", "to", "i", "you", "we", "my", "your", "our", "me",
}


def topic_slug_from_text(text):
    """Turn free text into a clean topic slug, dropping filler/question
    words but keeping meaningful ones (so 'time' in 'lunch time' stays).
    Falls back to every word if stripping stopwords would leave nothing.
    """
    words = re.findall(r"[a-zA-Z0-9']+", text.lower())
    kept = [w for w in words if w not in _STOPWORDS]
    return re.sub(r"[^a-z0-9]+", "-", " ".join(kept or words)).strip("-")


def try_statement(text):
    """Detect a one-shot declarative fact: 'lunch time is 1 PM',
    'the wifi password is X'. Returns (subject, value) or (None, None).

    Deliberately conservative: skipped entirely for anything ending in
    '?', since that's a question, not a new fact, even if it happens to
    contain a copula ("what is the wifi password?" must NOT be read as
    subject='what', value='the wifi password?').
    """
    text = text.strip()
    if text.endswith("?"):
        return None, None
    m = _STATEMENT_RE.match(text)
    if not m:
        return None, None
    subject, value = m.group(1).strip(), m.group(2).strip()
    if not subject or not value or subject.lower() in _STOPWORDS:
        return None, None
    return subject, value


def try_correction(text):
    """Return the corrected value if text reads like a correction, else None.
    Also strips a leading '<subject> is/are/was' clause if present, so
    "actually the wifi password is X" yields just "X", not the full clause.
    """
    m = _CORRECTION_RE.match(text.strip())
    if not m or not m.group(1).strip():
        return None
    value = m.group(1).strip()
    m2 = _LEADING_CLAUSE_RE.match(value)
    return m2.group(1).strip() if m2 else value


def is_chit_chat(text):
    return bool(_GREETING_RE.match(text.strip()) or
                _THANKS_RE.match(text.strip()) or _BYE_RE.match(text.strip()))


def phrase_chat(text):
    t = text.strip()
    if _THANKS_RE.match(t):
        return random.choice([
            "Anytime! Ask me anything about campus, or correct me if I'm wrong.",
            "You're welcome — happy to help.",
        ])
    if _BYE_RE.match(t):
        return random.choice(["See you around!", "Bye — come back if you need anything."])
    return random.choice([
        "Hey! Ask me about campus stuff — library hours, wifi, the bus, and so on.",
        "Hi there. I learn from corrections, so feel free to fix me if I'm wrong.",
    ])


def phrase_answer(value):
    return random.choice([
        value,
        f"It's {value}.",
        f"That would be {value}.",
        f"Here you go: {value}.",
    ])


def phrase_unknown():
    return random.choice([
        "I don't know this yet — what's the right answer?",
        "That one's new to me. Could you teach me?",
        "I'm not sure about that. What should the answer be?",
    ])


def phrase_corrected(value):
    return random.choice([
        f"Got it, updated to {value}.",
        f"Thanks — corrected to {value}.",
        f"Updated. It's {value} now.",
    ])


def phrase_learned(value):
    return random.choice([
        f"Learned it: {value}.",
        f"Noted — {value}.",
        f"Thanks, I'll remember: {value}.",
    ])
