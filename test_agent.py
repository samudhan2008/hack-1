import tempfile, unittest, pathlib
from agent import Agent

class T(unittest.TestCase):
    def setUp(self):
        d = pathlib.Path(tempfile.mkdtemp())
        self.a = Agent(kb=d / "kb.metta", audit=d / "audit.jsonl")

    def test_starts_wrong(self):
        self.assertEqual(self.a.belief("library-closing-time"), "5:00 PM")

    def test_correction_shows_diff(self):
        diff, rec = self.a.learn("library-closing-time", "8:00 PM")
        self.assertIn('-(= (answer library-closing-time) "5:00 PM")', diff)
        self.assertIn('+(= (answer library-closing-time) "8:00 PM")', diff)
        self.assertEqual(rec["old"], "5:00 PM")

    def test_persists_across_restart(self):
        self.a.learn("library-closing-time", "8:00 PM")
        b = Agent(kb=self.a.kb, audit=self.a.audit)
        self.assertEqual(b.belief("library-closing-time"), "8:00 PM")
        self.assertEqual(len(b.history()), 1)

    def test_unknown_topic_is_learned(self):
        self.assertIsNone(self.a.ask("Where is parking?")["answer"])
        self.a.learn("parking", "Behind Block C")
        self.assertEqual(self.a.ask("Where is parking?")["answer"], "Behind Block C")

    def test_same_value_noop(self):
        self.assertEqual(self.a.learn("library-closing-time", "5:00 PM"), ("", None))

    def test_rejects_empty(self):
        with self.assertRaises(ValueError):
            self.a.learn("x", "  ")

    def test_new_topics_are_seeded(self):
        for topic in ("wifi-password", "helpdesk-hours",
                      "registration-deadline", "bus-route"):
            self.assertIsNotNone(self.a.belief(topic))

    def test_new_topic_keyword_routing(self):
        self.assertEqual(self.a.ask("What's the wifi password?")["topic"],
                          "wifi-password")
        self.assertEqual(self.a.ask("When's the registration deadline?")["topic"],
                          "registration-deadline")
        self.assertEqual(self.a.ask("What time does the bus come?")["topic"],
                          "bus-route")

if __name__ == "__main__":
    unittest.main()
