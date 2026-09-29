import unittest
import local_nlp as nlp


class T(unittest.TestCase):
    def test_correction_variants(self):
        cases = {
            "no, 8:00 PM": "8:00 PM",
            "no 8:00 PM": "8:00 PM",
            "actually it's 8pm": "it's 8pm",
            "that's wrong, it's 8pm": "it's 8pm",
            "wrong, 8pm": "8pm",
            "incorrect: 8pm": "8pm",
        }
        for text, expected in cases.items():
            self.assertEqual(nlp.try_correction(text), expected, text)

    def test_non_correction_returns_none(self):
        self.assertIsNone(nlp.try_correction("when does the library close?"))
        self.assertIsNone(nlp.try_correction("noodles are great"))  # doesn't false-match "no"

    def test_strips_leading_subject_is_clause(self):
        self.assertEqual(
            nlp.try_correction("actually the wifi password is Campus@2026"),
            "Campus@2026")
        self.assertEqual(
            nlp.try_correction("no, the deadline is October 5th"),
            "October 5th")
        # no copula present -> value returned as-is
        self.assertEqual(nlp.try_correction("no, 8:00 PM"), "8:00 PM")

    def test_topic_slug_from_question_drops_filler_words(self):
        self.assertEqual(nlp.topic_slug_from_text("when is the lunch time"),
                          "lunch-time")
        self.assertEqual(nlp.topic_slug_from_text("what is the closing time"),
                          "closing-time")
        # falls back to every word if stopword-stripping empties it out
        self.assertEqual(nlp.topic_slug_from_text("what is the"), "what-is-the")

    def test_statement_detects_one_shot_new_facts(self):
        self.assertEqual(nlp.try_statement("lunch time is 1 PM"),
                          ("lunch time", "1 PM"))
        self.assertEqual(nlp.try_statement("the wifi password is Campus@2026"),
                          ("wifi password", "Campus@2026"))

    def test_statement_never_fires_on_questions(self):
        # Even without a '?', an interrogative subject must be rejected —
        # this is the main guard, since users often skip question marks.
        self.assertEqual(nlp.try_statement("what is the wifi password"), (None, None))
        self.assertEqual(nlp.try_statement("when is the lunch time"), (None, None))
        # and an explicit '?' is rejected regardless of phrasing
        self.assertEqual(nlp.try_statement("lunch time is 1 PM?"), (None, None))

    def test_chit_chat_detection(self):
        for text in ["hi", "hello there", "hey!", "thanks!", "thank you", "bye"]:
            self.assertTrue(nlp.is_chit_chat(text), text)
        self.assertFalse(nlp.is_chit_chat("when does the library close?"))

    def test_phrasing_helpers_include_the_value(self):
        self.assertIn("8:00 PM", nlp.phrase_answer("8:00 PM"))
        self.assertIn("8:00 PM", nlp.phrase_corrected("8:00 PM"))
        self.assertIn("8:00 PM", nlp.phrase_learned("8:00 PM"))
        self.assertTrue(nlp.phrase_unknown())  # just needs to return something


if __name__ == "__main__":
    unittest.main()
