from __future__ import annotations

import unittest
from pathlib import Path
import sys
import io
import os
from unittest.mock import patch, MagicMock

# Ensure we can find scripts
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PACKAGE_ROOT / "orchestrator" / "scripts"
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import check_setup

class TestCheckSetup(unittest.TestCase):

    @patch("shutil.which")
    @patch("pathlib.Path.exists")
    @patch("subprocess.run")
    @patch("os.environ", {})
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_check_all_missing(self, mock_stdout, mock_run, mock_exists, mock_which) -> None:
        """Test the worst-case scenario: nothing is installed or configured."""
        # 1. Setup mocks
        mock_which.return_value = None # Nothing installed
        mock_exists.return_value = False # No files exist
        
        # 2. Run check
        check_setup.check()
        
        output = mock_stdout.getvalue()
        
        # 3. Verify core missing items and remediation commands
        self.assertIn("❌ Homebrew", output)
        self.assertIn("INSTALL: /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"", output)
        
        self.assertIn("❌ Node.js", output)
        self.assertIn("INSTALL: brew install node", output)
        
        self.assertIn("❌ GitHub CLI (gh)", output)
        self.assertIn("❌ CRITICAL ERROR: No AI providers found", output)
        self.assertIn("OPTIONAL MCP / CODEX EXTENSIONS", output)
        self.assertIn("○ GitHub MCP/plugin", output)
        self.assertIn("recommended, not required", output)
        
        self.assertIn("💡 NEXT STEP: Create", output)

    @patch("shutil.which")
    @patch("pathlib.Path.exists")
    @patch("subprocess.run")
    @patch("os.environ", {"GEMINI_API_KEY": "fake_key"})
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_check_partially_ready(self, mock_stdout, mock_run, mock_exists, mock_which) -> None:
        """Test scenario where some things are ready (Gemini key set, core tools installed)."""
        # 1. Setup mocks
        # Tools are installed
        mock_which.side_effect = lambda x: "/usr/bin/" + x if x in ["brew", "node", "xcodebuild", "gh"] else None
        # Some files exist
        mock_exists.side_effect = lambda: True # Simplified for this test
        
        # Mock gh auth status to be SUCCESS
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_run.return_value = mock_res
        
        # 2. Run check
        with patch("check_setup.check_file_content", return_value=True):
            check_setup.check()
        
        output = mock_stdout.getvalue()
        
        # 3. Verify
        self.assertIn("✅ Homebrew", output)
        self.assertIn("✅ Node.js", output)
        self.assertIn("✅ GitHub Auth session", output)
        self.assertIn("✅ READY: At least one AI provider is configured.", output)
        self.assertIn("✅ Manual API Keys", output)

    @patch("shutil.which")
    @patch("pathlib.Path.exists")
    @patch("subprocess.run")
    @patch("os.environ", {"GEMINI_API_KEY": "fake_key"})
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_check_detects_optional_codex_integrations(self, mock_stdout, mock_run, mock_exists, mock_which) -> None:
        mock_which.side_effect = lambda x: "/usr/bin/" + x if x in ["brew", "node", "xcodebuild", "gh"] else None
        mock_exists.side_effect = lambda: True
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_run.return_value = mock_res
        config_text = """
[mcp_servers.xcodebuildmcp]
command = "npx"
[mcp_servers.playwright]
command = "npx"
[plugins."github@openai-curated"]
enabled = true
[plugins."sentry@openai-curated"]
enabled = true
"""

        with patch("check_setup.check_file_content", return_value=True), \
             patch("check_setup.read_codex_config_text", return_value=config_text):
            check_setup.check()

        output = mock_stdout.getvalue()
        self.assertIn("✅ GitHub MCP/plugin", output)
        self.assertIn("✅ XcodeBuildMCP / iOS plugin", output)
        self.assertIn("✅ Sentry MCP/plugin", output)
        self.assertIn("✅ Playwright MCP", output)

    @patch("shutil.which")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_check_ollama_only(self, mock_stdout, mock_which) -> None:
        """Verify that having only Ollama (no keys) results in a READY state."""
        # 1. Setup mocks
        mock_which.side_effect = lambda x: "/usr/local/bin/ollama" if x == "ollama" else None
        
        # Mock env and settings to have NO keys
        with patch.dict(os.environ, {}, clear=True), \
             patch("pathlib.Path.exists", return_value=False): # No settings.json
            
            check_setup.check()
            
        output = mock_stdout.getvalue()
        
        # 3. Verify
        self.assertIn("✅ Ollama (Local AI)", output)
        self.assertIn("✅ READY: At least one AI provider is configured.", output)
        self.assertIn("❌ Manual API Keys", output) # Should be red but overall state is ready

if __name__ == "__main__":
    unittest.main()
