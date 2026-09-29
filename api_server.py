"""Campus Helper — as an actual HTTP API.

Zero external dependencies, zero API keys: uses only Python's standard
library (http.server). Run it, then either open http://localhost:8000
in a browser for a small chat page, or call the JSON endpoints directly
(see curl examples in README.md).

Endpoints
---------
GET  /                      simple browser chat UI
GET  /health                {"status": "ok"}
GET  /rules                 {"rules": "<kb.metta contents>"}
GET  /history               {"history": [ ...audit records... ]}
POST /ask     {"question"}  -> {"answer","topic","trail","reply"}
POST /correct {"topic"?,"value"}  -> {"diff","record","reply"}
                             (topic defaults to whatever /ask last matched)
POST /teach   {"topic","value"}   -> {"diff","record","reply"}
POST /message {"text"}      -> one unified conversational endpoint that
                             mirrors the CLI: detects corrections/chit-chat/
                             clarifying answers itself. Good for a UI that
                             just wants to send whatever the user typed.

Every fact, diff, and audit entry comes straight from agent.Agent — this
file only does HTTP plumbing and reply-wording (via local_nlp), same as
the CLI in agent.py.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from agent import Agent, slug
import local_nlp as nlp

PORT = 8000

agent_lock = threading.Lock()          # one shared Agent, guarded for
agent = Agent()                        # concurrent requests
pending = {"topic": None}              # topic awaiting a /message-taught answer

INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SJIT Campus Helper</title>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#f3f5f9; --card:#fff; --ink:#1b2333; --muted:#6b7385; --line:#e4e8f0;
  --brand:#2f5bea; --brand-ink:#fff; --agent:#eef1f7; --add:#e6f6ec; --add-ink:#17663a;
  --del:#fdecec; --del-ink:#a12828;
}
*{box-sizing:border-box}
html,body{height:100%;margin:0}
body{background:var(--bg);color:var(--ink);font-family:"Plus Jakarta Sans",system-ui,-apple-system,"Segoe UI",sans-serif;
  display:flex;justify-content:center;padding:24px 16px}
.app{width:100%;max-width:720px;height:calc(100% - 0px);max-height:860px;display:flex;flex-direction:column;
  background:var(--card);border:1px solid var(--line);border-radius:20px;box-shadow:0 10px 40px rgba(30,45,90,.08);overflow:hidden}
header{padding:18px 22px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:12px}
.logo{width:40px;height:40px;border-radius:12px;background:var(--brand);color:#fff;display:grid;place-items:center;font-weight:700;font-size:14px}
header h1{font-size:17px;margin:0;font-weight:700}
header p{margin:2px 0 0;font-size:12.5px;color:var(--muted)}
.status{margin-left:auto;display:flex;align-items:center;gap:6px;font-size:12px;color:var(--muted)}
.status i{width:8px;height:8px;border-radius:50%;background:#2fb26a;display:block}
#log{flex:1;overflow-y:auto;padding:22px;display:flex;flex-direction:column;gap:12px;scroll-behavior:smooth}
.row{display:flex;flex-direction:column;max-width:82%}
.row.user{align-self:flex-end;align-items:flex-end}
.row.agent{align-self:flex-start;align-items:flex-start}
.bubble{padding:10px 15px;border-radius:18px;font-size:15px;line-height:1.5;white-space:pre-wrap;word-wrap:break-word}
.user .bubble{background:var(--brand);color:var(--brand-ink);border-bottom-right-radius:6px}
.agent .bubble{background:var(--agent);border-bottom-left-radius:6px}
.agent .bubble.learned{background:#eaf0ff;color:#1f3fa8}
.meta{font-size:11px;color:var(--muted);margin:4px 6px 0}
details.diff{margin-top:8px;width:100%;min-width:300px;border:1px solid var(--line);border-radius:12px;background:#fafbfd;font-size:13px}
details.diff summary{cursor:pointer;padding:9px 13px;font-weight:600;color:var(--muted);list-style:none;display:flex;align-items:center;gap:8px}
details.diff summary::-webkit-details-marker{display:none}
details.diff summary::before{content:"▸";transition:transform .15s}
details.diff[open] summary::before{transform:rotate(90deg)}
.diff pre{margin:0;padding:6px 0 10px;overflow-x:auto;font:12px/1.6 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.diff .ln{display:block;padding:0 13px;white-space:pre}
.diff .add{background:var(--add);color:var(--add-ink)}
.diff .del{background:var(--del);color:var(--del-ink)}
.diff .hunk{color:var(--muted)}
.typing{display:flex;gap:4px;padding:14px 16px}
.typing span{width:7px;height:7px;border-radius:50%;background:#9aa3b8;animation:b 1s infinite}
.typing span:nth-child(2){animation-delay:.15s}.typing span:nth-child(3){animation-delay:.3s}
@keyframes b{0%,60%,100%{transform:translateY(0);opacity:.5}30%{transform:translateY(-4px);opacity:1}}
.chips{display:flex;flex-wrap:wrap;gap:8px;padding:0 22px 12px}
.chips button{border:1px solid var(--line);background:#fff;color:var(--ink);border-radius:999px;padding:7px 13px;font:500 13px inherit;font-family:inherit;cursor:pointer}
.chips button:hover{border-color:var(--brand);color:var(--brand)}
form{display:flex;gap:10px;padding:14px 18px;border-top:1px solid var(--line);background:#fff}
input{flex:1;border:1px solid var(--line);background:var(--bg);border-radius:999px;padding:12px 18px;font:15px inherit;font-family:inherit;color:var(--ink)}
input:focus{outline:2px solid var(--brand);outline-offset:1px;background:#fff}
button.send{border:0;background:var(--brand);color:#fff;border-radius:999px;padding:0 22px;font:600 14px inherit;font-family:inherit;cursor:pointer}
button.send:hover{filter:brightness(1.08)}
button.send:disabled{opacity:.5;cursor:default}
button:focus-visible{outline:2px solid var(--brand);outline-offset:2px}
@media(max-width:520px){body{padding:0}.app{border-radius:0;max-height:none;border:0}.row{max-width:92%}}
@media(prefers-reduced-motion:reduce){*{animation:none!important;scroll-behavior:auto!important}}
</style>
</head>
<body>
<main class="app">
  <header>
    <div class="logo">SJ</div>
    <div>
      <h1>SJIT Campus Helper</h1>
      <p>Ask about campus. If I'm wrong, say &ldquo;no, &hellip;&rdquo; and I'll learn.</p>
    </div>
    <div class="status"><i></i>Local, no API key</div>
  </header>

  <div id="log" aria-live="polite"></div>

  <div class="chips" id="chips">
    <button type="button">What bus routes are available?</button>
    <button type="button">When is the lunch time?</button>
    <button type="button">Registration deadline?</button>
  </div>

  <form id="form">
    <input id="input" autocomplete="off" placeholder="Ask something, or say &ldquo;no, &hellip;&rdquo; to correct me" aria-label="Message">
    <button class="send" id="send" type="submit">Send</button>
  </form>
</main>

<script>
/* ---- Wired to this project's own local HTTP API — no external AI, no key ---- */
const API_URL = "/message";                       // this server's unified chat endpoint
const buildBody = (text) => ({ text: text });      // /message expects {"text": "..."}
/* /message responds with { "reply": "...", "diff": "...optional unified diff..." }
   which is exactly what the parser below reads. */

const log = document.getElementById("log");
const form = document.getElementById("form");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send");
const chips = document.getElementById("chips");

const time = () => new Date().toLocaleTimeString([], {hour:"numeric", minute:"2-digit"});

function addMsg(role, text, opts = {}) {
  const row = document.createElement("div");
  row.className = "row " + role;
  const b = document.createElement("div");
  b.className = "bubble" + (opts.learned ? " learned" : "");
  b.textContent = text;
  row.appendChild(b);
  if (opts.diff) row.appendChild(renderDiff(opts.diff));
  const m = document.createElement("div");
  m.className = "meta";
  m.textContent = time();
  row.appendChild(m);
  log.appendChild(row);
  log.scrollTop = log.scrollHeight;
  return row;
}

function renderDiff(text) {
  const d = document.createElement("details");
  d.className = "diff";
  d.innerHTML = "<summary>What changed in my rules</summary>";
  const pre = document.createElement("pre");
  text.split("\\n").forEach(line => {
    const s = document.createElement("span");
    s.className = "ln" + (line.startsWith("+++") || line.startsWith("---") || line.startsWith("@@") ? " hunk"
      : line.startsWith("+") ? " add" : line.startsWith("-") ? " del" : "");
    s.textContent = line || " ";
    pre.appendChild(s);
  });
  d.appendChild(pre);
  return d;
}

function showTyping() {
  const row = document.createElement("div");
  row.className = "row agent";
  row.innerHTML = '<div class="bubble typing"><span></span><span></span><span></span></div>';
  log.appendChild(row);
  log.scrollTop = log.scrollHeight;
  return row;
}

async function send(text) {
  text = text.trim();
  if (!text) return;
  addMsg("user", text);
  input.value = "";
  chips.style.display = "none";
  sendBtn.disabled = true;
  const typing = showTyping();
  try {
    const res = await fetch(API_URL, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(buildBody(text))
    });
    if (!res.ok) throw new Error("Server returned " + res.status);
    const data = await res.json();
    const reply = data.reply ?? data.answer ?? data.response ?? "";
    const diff = data.rule_diff ?? data.diff ?? "";
    typing.remove();
    addMsg("agent", reply, { diff, learned: /^learned it/i.test(reply) });
  } catch (err) {
    typing.remove();
    addMsg("agent", "I couldn't reach the helper (" + err.message + "). Check that the local server is running.");
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
}

form.addEventListener("submit", e => { e.preventDefault(); send(input.value); });
chips.addEventListener("click", e => { if (e.target.tagName === "BUTTON") send(e.target.textContent); });
addMsg("agent", "Hi! I can answer questions about SJIT campus. If I don't know something, you can teach me.");
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # keep the console quiet; remove this line to see request logs

    def _send_json(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, body):
        data = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            return json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return {}

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            self._send_html(INDEX_HTML)
        elif path == "/health":
            self._send_json(200, {"status": "ok"})
        elif path == "/rules":
            with agent_lock:
                self._send_json(200, {"rules": agent.text()})
        elif path == "/history":
            with agent_lock:
                self._send_json(200, {"history": agent.history()})
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        data = self._read_json()
        handlers = {"/ask": self._ask, "/correct": self._correct,
                    "/teach": self._teach, "/message": self._message}
        fn = handlers.get(path)
        if fn is None:
            self._send_json(404, {"error": "not found"})
            return
        with agent_lock:
            fn(data)

    # ---- individual endpoints -------------------------------------------
    def _ask(self, data):
        question = (data.get("question") or "").strip()
        if not question:
            self._send_json(400, {"error": "question is required"}); return
        r = agent.ask(question)
        reply = nlp.phrase_answer(r["answer"]) if r["answer"] else nlp.phrase_unknown()
        self._send_json(200, {**r, "reply": reply})

    def _correct(self, data):
        topic = data.get("topic") or agent.last_topic
        value = (data.get("value") or "").strip()
        if not topic or not value:
            self._send_json(400, {"error": "value is required (and topic, "
                                   "unless you've /ask'd something already)"})
            return
        diff, record = agent.learn(topic, value, "api correction")
        self._send_json(200, {"diff": diff, "record": record,
                               "reply": nlp.phrase_corrected(value)})

    def _teach(self, data):
        topic = (data.get("topic") or "").strip()
        value = (data.get("value") or "").strip()
        if not topic or not value:
            self._send_json(400, {"error": "topic and value are required"}); return
        diff, record = agent.learn(topic, value, "api taught new fact")
        self._send_json(200, {"diff": diff, "record": record,
                               "reply": nlp.phrase_learned(value)})

    def _message(self, data):
        """One conversational endpoint: mirrors the CLI's logic exactly,
        entirely locally (regex + templates, no external AI)."""
        text = (data.get("text") or "").strip()
        if not text:
            self._send_json(400, {"error": "text is required"}); return

        if nlp.is_chit_chat(text):
            self._send_json(200, {"reply": nlp.phrase_chat(text)}); return

        if pending["topic"]:
            topic = pending["topic"]; pending["topic"] = None
            diff, record = agent.learn(topic, text, "answer to clarifying question")
            self._send_json(200, {"reply": nlp.phrase_learned(text),
                                   "diff": diff, "record": record})
            return

        correction = nlp.try_correction(text)
        if correction:
            target = agent.find_topic(text) or agent.last_topic
            if target:
                diff, record = agent.learn(target, correction, "user correction")
                self._send_json(200, {"reply": nlp.phrase_corrected(correction),
                                       "diff": diff, "record": record})
                return

        subject, value = nlp.try_statement(text)
        if subject and value:
            new_topic = nlp.topic_slug_from_text(subject)
            if agent.belief(new_topic) is None:   # only auto-add genuinely new facts
                diff, record = agent.learn(new_topic, value, "auto-added new fact")
                self._send_json(200, {"reply": nlp.phrase_learned(value),
                                       "diff": diff, "record": record})
                return
            # topic already known -> fall through, treat as a question
            # instead of silently overwriting existing data

        r = agent.ask(text)
        if r["answer"]:
            self._send_json(200, {**r, "reply": nlp.phrase_answer(r["answer"])})
        else:
            pending["topic"] = nlp.topic_slug_from_text(text) if r["topic"] is None else r["topic"]
            self._send_json(200, {**r, "reply": nlp.phrase_unknown()})


def run(port=PORT):
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Campus Helper API running at http://localhost:{port}")
    print("Open that URL in a browser, or POST JSON to /ask, /correct, /teach, /message.")
    print("Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    run()
