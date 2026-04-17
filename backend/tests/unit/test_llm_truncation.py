"""Unit tests for LLM truncation heuristics."""

import unittest

from app.llm import _appears_truncated


class TruncationHeuristicTests(unittest.TestCase):
    def test_empty_education_is_not_treated_as_truncation_by_itself(self):
        payload = {
            "summary": "Backend engineer",
            "workExperience": [{"title": "Engineer"}],
            "education": [],
        }

        self.assertFalse(_appears_truncated(payload))


if __name__ == "__main__":
    unittest.main()
