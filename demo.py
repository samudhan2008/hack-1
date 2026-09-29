"""Scripted demo for the 3-minute video. Run: python demo.py"""
import tempfile, pathlib
from agent import Agent

d = pathlib.Path(tempfile.mkdtemp())
a = Agent(kb=d / "kb.metta", audit=d / "audit.jsonl")

def say(q):
    print(f"\nyou> {q}")
    r = a.ask(q)
    for s in r["trail"]: print("  [why]", s)
    print("agent>", r["answer"] or "I don't know. What is the right answer?")

# 1. Wrong belief gets corrected
say("When does the library close?")
print("\nyou> no, 8:00 PM")
diff, _ = a.learn("library-closing-time", "8:00 PM")
print("agent> Corrected. Rule diff:\n" + diff)
say("When does the library close?")

# 2. Persistence across a restart
print("\n--- restart: new Agent, same files (persistence) ---")
a2 = Agent(kb=d / "kb.metta", audit=d / "audit.jsonl")
print("agent(after restart) believes:", a2.belief("library-closing-time"))

# 3. Low-confidence belief also gets corrected
print("\nyou> What's the registration deadline?")
r = a.ask("What's the registration deadline?")
for s in r["trail"]: print("  [why]", s)
print("agent>", r["answer"], "(low confidence — likely to be wrong)")
print("\nyou> no, October 2nd, 11:59 PM")
diff, _ = a.learn("registration-deadline", "October 2nd, 11:59 PM")
print("agent> Corrected. Rule diff:\n" + diff)

# 4. Brand-new topic: agent has no rule, asks, then learns it
say("Where is the parking lot?")
diff, _ = a.learn("parking-lot", "Behind Block C")
print("agent> Learned something new. Rule diff:\n" + diff)
say("Where is the parking lot?")

# 5. Show the full audit trail at the end
print("\n--- full audit trail (every correction, in order) ---")
for h in a.history():
    print(f"[{h['time']}] {h['topic']}: {h['old']!r} -> {h['new']!r}  ({h['reason']})")
