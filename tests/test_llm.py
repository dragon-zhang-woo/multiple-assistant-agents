from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from research_team.llm import missing_key_message, resolve_provider


class ProviderTests(unittest.TestCase):
    def test_auto_prefers_deepseek_key(self) -> None:
        with patch.dict(
            os.environ,
            {"DEEPSEEK_API_KEY": "deep", "DASHSCOPE_API_KEY": "dash"},
            clear=True,
        ):
            provider = resolve_provider("auto")

        self.assertIsNotNone(provider)
        self.assertEqual(provider[0], "deepseek")
        self.assertEqual(provider[1], "deep")

    def test_dashscope_can_be_selected_explicitly(self) -> None:
        with patch.dict(
            os.environ,
            {"DEEPSEEK_API_KEY": "deep", "DASHSCOPE_API_KEY": "dash"},
            clear=True,
        ):
            provider = resolve_provider("dashscope")

        self.assertIsNotNone(provider)
        self.assertEqual(provider[0], "dashscope")
        self.assertEqual(provider[1], "dash")

    def test_missing_deepseek_message_is_specific(self) -> None:
        self.assertIn("DEEPSEEK_API_KEY", missing_key_message("deepseek"))


if __name__ == "__main__":
    unittest.main()
