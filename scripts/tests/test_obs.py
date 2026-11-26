import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import obs


class PlatformTests(unittest.TestCase):
    def test_detects_windows_claude_code_path(self):
        with patch.object(obs, "SKILL_DIR", r"C:\Users\PM\.claude\skills\eol-launcher"), \
                patch.dict(os.environ, {}, clear=True):
            self.assertEqual(obs._platform(), "claude-code")

    def test_detects_windows_cursor_path(self):
        with patch.object(obs, "SKILL_DIR", r"C:\Users\PM\.cursor\skills\eol-launcher"), \
                patch.dict(os.environ, {}, clear=True):
            self.assertEqual(obs._platform(), "cursor")

    def test_claude_code_environment_takes_precedence(self):
        with patch.object(obs, "SKILL_DIR", r"C:\Users\PM\.cursor\skills\eol-launcher"), \
                patch.dict(os.environ, {"CLAUDECODE": "1"}, clear=True):
            self.assertEqual(obs._platform(), "claude-code")
