# The Agent That Grows Up
MeTTa Foundation · Track 02 · Challenge 01

## Problem
Static AI only knows what it was trained on. When it is wrong, you cannot see
what it believed or how it changed.

## Solution
A campus-helper agent that starts with a **wrong belief** (library closes at
5 PM), gets **corrected** by a user, and prints the **literal diff** between its
old rule and its new rule. It also flags uncertainty on unknown topics, asks a
clarifying question, and permanently learns the answer.

## How it works
- Beliefs are MeTTa-style rules in `kb.metta`, e.g. `(= (answer library-closing-time) "5:00 PM")`.
- Every answer prints a visible "why" trail (which rule matched, its confidence).
- `learn()` rewrites the rule, returns a unified diff, and appends to `audit.jsonl`.
- Rules and audit trail are files, so the agent remembers across sessions.

## Two ways to run it
Both are **fully local — no external AI API, no API key, no internet
connection required.** Free-form phrasing and varied replies come from
`local_nlp.py` (plain regex + template pools), not a model call.

**1. Interactive CLI**
    python agent.py
Ask naturally ("when does the library close?"), correct it naturally
("no, 8:00 PM" / "actually it's open till 8" / "that's wrong, 8pm"), or
just chat ("hi", "thanks"). Commands: `/rules`, `/history`, `/trail`, `/quit`.

**2. A real HTTP API — `python api_server.py`**
This is what "generative AI assistant" now means here: the program *is*
an API, not a wrapper around someone else's. It uses only Python's
standard library (`http.server`), so there's nothing to install.

    python api_server.py
    # -> Campus Helper API running at http://localhost:8000

Open `http://localhost:8000` in a browser for a built-in chat page (with
suggestion chips, a typing indicator, and a collapsible "what changed in
my rules" diff view under each correction), or call it directly:

    curl -X POST localhost:8000/message -H "Content-Type: application/json" \
         -d '{"text": "when does the library close?"}'

    curl -X POST localhost:8000/message -H "Content-Type: application/json" \
         -d '{"text": "actually the wifi password is Campus@2026"}'

    curl -X POST localhost:8000/ask -H "Content-Type: application/json" \
         -d '{"question": "what is the wifi password?"}'

    curl -X POST localhost:8000/teach -H "Content-Type: application/json" \
         -d '{"topic": "parking-lot", "value": "Behind Block C"}'

    curl localhost:8000/rules
    curl localhost:8000/history

Endpoints: `GET /health`, `GET /rules`, `GET /history`,
`POST /ask {question}`, `POST /correct {topic?, value}`,
`POST /teach {topic, value}`, `POST /message {text}` (one unified
conversational endpoint that mirrors the CLI). Every fact, diff, and audit
entry comes straight from `agent.Agent` — the server only does HTTP
plumbing and reply-wording, exactly like the CLI.

## Run
    python demo.py            # scripted, offline demo (use this for the video)
    python agent.py           # interactive CLI
    python api_server.py      # HTTP API + browser chat page
    python -m unittest discover   # all tests, including a live API test

## What's next
- Replace the file store with Omega's stateful memory (see TODO below).
- Run the rules through the MeTTa/Hyperon runtime (`hyperon` package).
- Conflict handling when two users give different corrections.

## TODO (24 HR track): Omega integration
Omega is mandatory for the 24 HR track. Wire `Agent.learn()` and
`Agent.ask()` to Omega's memory/reasoning API per the hackathon docs.

## AI Disclosure
Claude (Anthropic) was used to draft the initial code, tests and this README.
The team reviewed, ran and modified it. (Edit this to match what you really did.)

The shipped agent itself has no runtime AI dependency: natural-language
understanding (`local_nlp.py`) is plain regex and template phrasing, and
`api_server.py` is a standard-library HTTP server. Nothing calls an
external model or needs an API key.
