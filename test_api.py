import json
import tempfile
import threading
import time
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

import agent as agent_module
import api_server


def request(method, path, body=None):
    url = f"http://127.0.0.1:{PORT}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                  headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.status, json.loads(resp.read())


PORT = 8931  # fixed test port, unlikely to clash


class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Point the server at a throwaway kb/audit so tests don't touch
        # the real project files, then start it on a background thread.
        d = tempfile.mkdtemp()
        api_server.agent = agent_module.Agent(kb=f"{d}/kb.metta", audit=f"{d}/audit.jsonl")
        api_server.pending["topic"] = None
        cls.server = ThreadingHTTPServer(("127.0.0.1", PORT), api_server.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.2)  # give it a moment to bind

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_health(self):
        status, data = request("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "ok")

    def test_ask_known_topic(self):
        status, data = request("POST", "/ask", {"question": "when does the library close?"})
        self.assertEqual(status, 200)
        self.assertEqual(data["answer"], "5:00 PM")
        self.assertIn("reply", data)

    def test_correct_defaults_topic_to_last_ask(self):
        request("POST", "/ask", {"question": "when does the library close?"})
        status, data = request("POST", "/correct", {"value": "8:00 PM"})
        self.assertEqual(status, 200)
        self.assertIn("8:00 PM", data["diff"])
        status, data = request("POST", "/ask", {"question": "when does the library close?"})
        self.assertEqual(data["answer"], "8:00 PM")

    def test_teach_new_topic(self):
        status, data = request("POST", "/teach",
                                {"topic": "parking-lot", "value": "Behind Block C"})
        self.assertEqual(status, 200)
        self.assertIn("Behind Block C", data["diff"])

    def test_message_full_conversation_flow(self):
        # unknown topic -> agent asks -> next message teaches it
        status, data = request("POST", "/message", {"text": "where is the gym?"})
        self.assertEqual(status, 200)
        self.assertIsNone(data["answer"])
        status, data = request("POST", "/message", {"text": "Behind the sports complex"})
        self.assertEqual(status, 200)
        self.assertIn("Behind the sports complex", data["diff"])

    def test_message_chit_chat(self):
        status, data = request("POST", "/message", {"text": "hi there"})
        self.assertEqual(status, 200)
        self.assertNotIn("diff", data)

    def test_correction_routes_to_topic_named_in_sentence_not_stale_last_topic(self):
        # Ask about the library first (sets last_topic = library-closing-time),
        # then correct a *different* topic in one sentence. It must update
        # wifi-password, not overwrite library-closing-time.
        _, before = request("POST", "/ask", {"question": "when does the library close?"})
        status, data = request("POST", "/message",
                                {"text": "actually the wifi password is Campus@2026"})
        self.assertEqual(status, 200)
        self.assertIn("Campus@2026", data["diff"])
        self.assertIn("+(= (answer wifi-password)", data["diff"])
        self.assertNotIn('-(= (answer library-closing-time)', data["diff"])
        _, after = request("POST", "/ask", {"question": "when does the library close?"})
        self.assertEqual(after["answer"], before["answer"])  # untouched by the wifi correction

    def test_history_and_rules_endpoints(self):
        status, data = request("GET", "/rules")
        self.assertEqual(status, 200)
        self.assertIn("library-closing-time", data["rules"])
        status, data = request("GET", "/history")
        self.assertEqual(status, 200)
        self.assertTrue(len(data["history"]) >= 1)

    def test_unknown_question_gets_a_clean_topic_name(self):
        # Reproduces the screenshot: "when is the lunch time" used to
        # become the topic "when-is-the-lunch-time". It should now be
        # just "lunch-time".
        status, data = request("POST", "/message", {"text": "when is the lunch time"})
        self.assertEqual(status, 200)
        self.assertIsNone(data["answer"])
        status, data = request("POST", "/message", {"text": "1 PM"})
        self.assertEqual(status, 200)
        self.assertIn("+(= (answer lunch-time) \"1 PM\")", data["diff"])
        self.assertNotIn("when-is-the-lunch-time", data["diff"])

    def test_one_shot_statement_auto_adds_new_fact(self):
        # No question first, no "teach me" round trip — just state it.
        status, data = request("POST", "/message",
                                {"text": "the gym opening time is 6 AM"})
        self.assertEqual(status, 200)
        self.assertIn("+(= (answer gym-opening-time) \"6 AM\")", data["diff"])
        status, data = request("POST", "/ask", {"question": "when is the gym opening time?"})
        self.assertEqual(data["answer"], "6 AM")

    def test_one_shot_statement_never_overwrites_existing_fact(self):
        # library-closing-time already exists. A bare statement about it
        # (no correction trigger word) must NOT silently change it —
        # only /correct or an explicit "no/actually ..." can.
        _, before = request("POST", "/ask", {"question": "when does the library close?"})
        status, data = request("POST", "/message",
                                {"text": "the library closing time is 11 PM"})
        self.assertEqual(status, 200)
        self.assertNotIn("diff", data)          # nothing was changed
        _, after = request("POST", "/ask", {"question": "when does the library close?"})
        self.assertEqual(after["answer"], before["answer"])


if __name__ == "__main__":
    unittest.main()
