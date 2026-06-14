from __future__ import annotations

import sys
import unittest
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PACKAGE_ROOT / "orchestrator" / "scripts"

if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

# Import model_registry after path setup
import model_registry

class ModelRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_home = Path(self.tmp_dir.name)
        # Clear cache before each test
        model_registry._ALL_MODELS_CACHE = None
        
    def tearDown(self):
        self.tmp_dir.cleanup()
        # Clear environment after each test
        if "ORCHESTRATOR_PROJECT_ROOT" in os.environ:
            del os.environ["ORCHESTRATOR_PROJECT_ROOT"]

    @patch("pathlib.Path.home")
    @patch("urllib.request.urlopen")
    def test_sync_models_success(self, mock_urlopen, mock_home):
        mock_home.return_value = self.tmp_home
        
        # Setup mock response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "models": [
                {
                    "id": "claude-opus-4-8",
                    "family": "claude",
                    "tier": "EXTREME",
                    "capabilities": ["reasoning", "coding"],
                    "cost_factor": 10.0,
                    "required_clis": ["claude"]
                }
            ]
        }).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        
        success, msg = model_registry.sync_models()
        
        self.assertTrue(success)
        self.assertIn("Successfully synced 1 models", msg)
        
        # Verify file creation
        config_path = self.tmp_home / ".orchestrator" / "custom_models.json"
        self.assertTrue(config_path.exists())
        
        data = json.loads(config_path.read_text())
        self.assertEqual(len(data["models"]), 1)
        self.assertEqual(data["models"][0]["id"], "claude-opus-4-8")
        
        # Verify cache invalidation and loading
        all_models = model_registry.get_all_models()
        model_ids = [m.id for m in all_models]
        self.assertIn("claude-opus-4-8", model_ids)

    @patch("pathlib.Path.home")
    @patch("urllib.request.urlopen")
    def test_sync_models_merges_with_existing(self, mock_urlopen, mock_home):
        mock_home.return_value = self.tmp_home
        
        # Create existing local custom model
        config_dir = self.tmp_home / ".orchestrator"
        config_dir.mkdir(parents=True)
        config_path = config_dir / "custom_models.json"
        config_path.write_text(json.dumps({
            "models": [
                {
                    "id": "my-local-model",
                    "tier": "LOW",
                    "capabilities": ["speed"]
                }
            ]
        }))
        
        # Setup mock response for new model
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "models": [
                {
                    "id": "claude-opus-4-8",
                    "tier": "EXTREME",
                    "capabilities": ["coding"]
                }
            ]
        }).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        
        success, msg = model_registry.sync_models()
        self.assertTrue(success)
        
        data = json.loads(config_path.read_text())
        ids = [m["id"] for m in data["models"]]
        self.assertIn("my-local-model", ids)
        self.assertIn("claude-opus-4-8", ids)

    @patch("pathlib.Path.home")
    @patch("urllib.request.urlopen")
    def test_sync_models_failure(self, mock_urlopen, mock_home):
        mock_home.return_value = self.tmp_home
        mock_urlopen.side_effect = Exception("Network error")
        
        success, msg = model_registry.sync_models()
        self.assertFalse(success)
        self.assertIn("Sync failed: Network error", msg)

if __name__ == "__main__":
    unittest.main()
