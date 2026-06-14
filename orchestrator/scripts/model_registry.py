#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any

# We use IntEnum to allow comparison (tier 1 < tier 2)
class ModelTier(IntEnum):
    EXTREME = 1  # Opus / O1
    HIGH = 2     # Pro / Sonnet
    MEDIUM = 3   # Flash / Haiku
    LOW = 4      # Lite / Small

class ModelCapability(Enum):
    REASONING = "reasoning"
    CODING = "coding"
    SPEED = "speed"
    CONTEXT = "context"
    VISION = "vision"

@dataclass
class ModelMetadata:
    id: str
    family: str
    tier: ModelTier
    capabilities: list[ModelCapability] = field(default_factory=list)
    cost_factor: float = 1.0
    aliases: list[str] = field(default_factory=list)
    required_clis: list[str] = field(default_factory=list)
    api_model_id: str | None = None
    reasoning_effort: str | None = None

MODELS = [
    ModelMetadata(
        id="claude-opus-4-8",
        family="claude",
        tier=ModelTier.EXTREME,
        capabilities=[ModelCapability.REASONING, ModelCapability.CODING, ModelCapability.CONTEXT],
        cost_factor=10.0,
        required_clis=["claude"]
    ),
    ModelMetadata(
        id="claude-opus-4-7",
        family="claude",
        tier=ModelTier.EXTREME,
        capabilities=[ModelCapability.REASONING, ModelCapability.CODING, ModelCapability.CONTEXT],
        cost_factor=10.0,
        required_clis=["claude"]
    ),
    ModelMetadata(
        id="claude-sonnet-4-6",
        family="claude",
        tier=ModelTier.HIGH,
        capabilities=[ModelCapability.CODING, ModelCapability.SPEED, ModelCapability.CONTEXT],
        cost_factor=5.0,
        aliases=["claude"],
        required_clis=["claude"]
    ),
    ModelMetadata(
        id="claude-haiku-4-5",
        family="claude",
        tier=ModelTier.MEDIUM,
        capabilities=[ModelCapability.SPEED],
        cost_factor=1.0,
        required_clis=["claude"]
    ),
    ModelMetadata(
        id="gemini-3.1-pro-preview",
        family="gemini",
        tier=ModelTier.HIGH,
        capabilities=[ModelCapability.REASONING, ModelCapability.CODING, ModelCapability.CONTEXT, ModelCapability.VISION],
        cost_factor=5.0,
        aliases=["gemini"],
        required_clis=["gemini"]
    ),
    ModelMetadata(
        id="gemini-3-flash-preview",
        family="gemini",
        tier=ModelTier.MEDIUM,
        capabilities=[ModelCapability.SPEED, ModelCapability.CONTEXT, ModelCapability.VISION],
        cost_factor=1.0,
        required_clis=["gemini"]
    ),
    ModelMetadata(
        id="gemini-3.1-flash-lite-preview",
        family="gemini",
        tier=ModelTier.LOW,
        capabilities=[ModelCapability.SPEED, ModelCapability.CONTEXT],
        cost_factor=0.5,
        required_clis=["gemini"]
    ),
    ModelMetadata(
        id="gpt-5.5",
        family="openai",
        tier=ModelTier.EXTREME,
        capabilities=[ModelCapability.REASONING, ModelCapability.CODING, ModelCapability.CONTEXT],
        cost_factor=10.0,
        reasoning_effort="high",
        required_clis=["codex"]
    ),
    ModelMetadata(
        id="gpt-5.5-high",
        family="openai",
        tier=ModelTier.EXTREME,
        capabilities=[ModelCapability.REASONING, ModelCapability.CODING, ModelCapability.CONTEXT],
        cost_factor=10.0,
        api_model_id="gpt-5.5",
        reasoning_effort="high",
        required_clis=["codex"]
    ),
    ModelMetadata(
        id="gpt-5.5-medium",
        family="openai",
        tier=ModelTier.HIGH,
        capabilities=[ModelCapability.REASONING, ModelCapability.CODING, ModelCapability.CONTEXT],
        cost_factor=5.0,
        api_model_id="gpt-5.5",
        reasoning_effort="medium",
        required_clis=["codex"]
    ),
    ModelMetadata(
        id="gpt-5.5-low",
        family="openai",
        tier=ModelTier.MEDIUM,
        capabilities=[ModelCapability.REASONING, ModelCapability.CODING, ModelCapability.CONTEXT],
        cost_factor=2.0,
        api_model_id="gpt-5.5",
        reasoning_effort="low",
        required_clis=["codex"]
    ),
    ModelMetadata(
        id="gpt-5.4",
        family="openai",
        tier=ModelTier.HIGH,
        capabilities=[ModelCapability.CODING, ModelCapability.REASONING, ModelCapability.SPEED],
        cost_factor=4.0,
        aliases=["codex"],
        required_clis=["codex"]
    ),
    ModelMetadata(
        id="gpt-5.4-mini",
        family="openai",
        tier=ModelTier.MEDIUM,
        capabilities=[ModelCapability.SPEED, ModelCapability.CODING],
        cost_factor=1.0,
        required_clis=["codex"]
    ),
    ModelMetadata(
        id="gpt-5.3-codex",
        family="openai",
        tier=ModelTier.MEDIUM,
        capabilities=[ModelCapability.CODING, ModelCapability.SPEED],
        cost_factor=2.0,
        required_clis=["codex"]
    ),
    ModelMetadata(
        id="gpt-5.2",
        family="openai",
        tier=ModelTier.HIGH,
        capabilities=[ModelCapability.REASONING, ModelCapability.SPEED],
        cost_factor=3.0,
        required_clis=["codex"]
    ),
    ModelMetadata(
        id="deepseek",
        family="deepseek",
        tier=ModelTier.HIGH,
        capabilities=[ModelCapability.CODING, ModelCapability.REASONING],
        cost_factor=2.0,
        required_clis=["ollama"]
    ),
    ModelMetadata(
        id="copilot",
        family="copilot",
        tier=ModelTier.HIGH,
        capabilities=[ModelCapability.CODING, ModelCapability.SPEED],
        cost_factor=0.0,
        required_clis=["gh"]
    ),
    ModelMetadata(
        id="opencode/big-pickle",
        family="opencode",
        tier=ModelTier.LOW,
        capabilities=[ModelCapability.CODING, ModelCapability.SPEED],
        cost_factor=1.0,
        aliases=["opencode", "big-pickle"],
        required_clis=["opencode"]
    ),
    ModelMetadata(
        id="opencode/deepseek-v4-flash-free",
        family="opencode",
        tier=ModelTier.LOW,
        capabilities=[ModelCapability.CODING, ModelCapability.SPEED],
        cost_factor=0.0,
        required_clis=["opencode"]
    ),
    ModelMetadata(
        id="opencode/nemotron-3-super-free",
        family="opencode",
        tier=ModelTier.LOW,
        capabilities=[ModelCapability.CODING, ModelCapability.SPEED],
        cost_factor=0.0,
        required_clis=["opencode"]
    ),
    ModelMetadata(
        id="opencode/qwen3.6-plus-free",
        family="opencode",
        tier=ModelTier.LOW,
        capabilities=[ModelCapability.CODING, ModelCapability.SPEED],
        cost_factor=0.0,
        required_clis=["opencode"]
    )
]

import json
import os
from pathlib import Path

# Legacy / Base IDs from llm.py that we should support as aliases or direct lookups
LEGACY_IDS = {
    "gemini": "gemini-3.1-pro-preview",
    "claude": "claude-sonnet-4-6",
    "codex": "gpt-5.4",
    "opencode": "opencode/big-pickle",
}

def load_custom_models() -> list[ModelMetadata]:
    """Loads custom models from ~/.orchestrator/custom_models.json or project config."""
    custom_models = []
    
    # Check global config
    global_config = Path.home() / ".orchestrator" / "custom_models.json"
    
    # Check project config if ORCHESTRATOR_PROJECT_ROOT is set
    project_config = None
    if "ORCHESTRATOR_PROJECT_ROOT" in os.environ:
        project_config = Path(os.environ["ORCHESTRATOR_PROJECT_ROOT"]) / ".orchestrator" / "config" / "custom_models.json"
        
    for config_path in [global_config, project_config]:
        if config_path and config_path.exists():
            try:
                data = json.loads(config_path.read_text(encoding="utf-8"))
                for item in data.get("models", []):
                    # Map string tiers back to Enums
                    tier_str = item.get("tier", "HIGH").upper()
                    tier = getattr(ModelTier, tier_str, ModelTier.HIGH)
                    
                    caps_str = item.get("capabilities", ["coding", "reasoning"])
                    caps = []
                    for c in caps_str:
                        try:
                            caps.append(ModelCapability(c.lower()))
                        except ValueError:
                            pass
                            
                    custom_models.append(ModelMetadata(
                        id=item["id"],
                        family=item.get("family", "custom"),
                        tier=tier,
                        capabilities=caps,
                        cost_factor=item.get("cost_factor", 1.0),
                        aliases=item.get("aliases", []),
                        required_clis=item.get("required_clis", []),
                        api_model_id=item.get("api_model_id"),
                        reasoning_effort=item.get("reasoning_effort")
                    ))
            except Exception as e:
                print(f"Warning: Failed to load custom models from {config_path}: {e}")
                
    return custom_models

_ALL_MODELS_CACHE = None

def get_all_models() -> list[ModelMetadata]:
    global _ALL_MODELS_CACHE
    if _ALL_MODELS_CACHE is None:
        _ALL_MODELS_CACHE = MODELS + load_custom_models()
    return _ALL_MODELS_CACHE

def get_model(model_id: str) -> ModelMetadata | None:
    # Check ID and aliases against all models
    all_m = get_all_models()
    for m in all_m:
        if model_id == m.id or model_id in m.aliases:
            return m
    return None

def heuristic_classify(model_id: str, family: str) -> ModelMetadata:
    """Best-effort classification of a raw model ID into our metadata structure."""
    m_id = model_id.lower()
    tier = ModelTier.HIGH # Default
    caps = [ModelCapability.CODING, ModelCapability.REASONING]
    
    # Tier mapping
    if any(x in m_id for x in ["opus", "o1", "gpt-5", "extreme"]):
        tier = ModelTier.EXTREME
    elif any(x in m_id for x in ["sonnet", "pro", "gpt-4", "high"]):
        tier = ModelTier.HIGH
    elif any(x in m_id for x in ["haiku", "flash", "gpt-3.5", "medium"]):
        tier = ModelTier.MEDIUM
    elif any(x in m_id for x in ["mini", "lite", "small", "low"]):
        tier = ModelTier.LOW
        
    # Capability mapping
    if any(x in m_id for x in ["vision", "visual"]):
        caps.append(ModelCapability.VISION)
    if any(x in m_id for x in ["context", "128k", "1m", "2m"]):
        caps.append(ModelCapability.CONTEXT)
    if "flash" in m_id or "turbo" in m_id:
        caps.append(ModelCapability.SPEED)
        
    # Cost factor (rough guess)
    cost = 1.0
    if tier == ModelTier.EXTREME: cost = 10.0
    elif tier == ModelTier.HIGH: cost = 5.0
    elif tier == ModelTier.MEDIUM: cost = 1.0
    elif tier == ModelTier.LOW: cost = 0.5
    
    # CLI mapping
    cli = family
    if family == "openai": cli = "codex"
    
    return ModelMetadata(
        id=model_id,
        family=family,
        tier=tier,
        capabilities=list(set(caps)),
        cost_factor=cost,
        required_clis=[cli],
        api_model_id=model_id
    )

def discover_from_sources() -> list[ModelMetadata]:
    """Pings various provider APIs to find new models."""
    import urllib.request
    import json
    discovered = []
    
    # 1. OpenAI
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        try:
            req = urllib.request.Request("https://api.openai.com/v1/models", 
                                         headers={"Authorization": f"Bearer {openai_key}"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                for m in data.get("data", []):
                    mid = m["id"]
                    if mid.startswith(("gpt-", "o1-")):
                        discovered.append(heuristic_classify(mid, "openai"))
        except: pass

    # 2. Gemini
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if gemini_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={gemini_key}"
            with urllib.request.urlopen(url, timeout=5) as resp:
                data = json.loads(resp.read())
                for m in data.get("models", []):
                    mid = m["name"].split("/")[-1]
                    if "gemini" in mid.lower():
                        discovered.append(heuristic_classify(mid, "gemini"))
        except: pass

    # 3. Ollama (Local)
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2) as resp:
            data = json.loads(resp.read())
            for m in data.get("models", []):
                mid = m["name"]
                discovered.append(heuristic_classify(mid, "ollama"))
    except: pass
    
    return discovered

def sync_models(live_discovery: bool = False) -> tuple[bool, str]:
    """
    Fetches latest model definitions and updates ~/.orchestrator/custom_models.json.
    - if live_discovery=True: Pings OpenAI/Gemini/Ollama APIs directly.
    - else: Fetches from the remote JSON registry.
    """
    import urllib.request
    import urllib.error
    import ssl
    
    global_config = Path.home() / ".orchestrator" / "custom_models.json"
    global_config.parent.mkdir(parents=True, exist_ok=True)
    
    new_models = []
    source_name = "remote registry"

    if live_discovery:
        source_name = "live provider APIs"
        new_models = discover_from_sources()
        if not new_models:
            return False, "Live discovery found no new models (check your API keys)."
    else:
        # Try to load registry URL from settings
        registry_url = "https://raw.githubusercontent.com/google/swift-orchestrator/main/orchestrator/config/models.json"
        settings_path = Path.home() / ".orchestrator" / "config" / "settings.json"
        if "ORCHESTRATOR_PROJECT_ROOT" in os.environ:
            p_settings = Path(os.environ["ORCHESTRATOR_PROJECT_ROOT"]) / ".orchestrator" / "config" / "settings.json"
            if p_settings.exists(): settings_path = p_settings
            
        if settings_path.exists():
            try:
                settings = json.loads(settings_path.read_text(encoding="utf-8"))
                registry_url = settings.get("model_registry_url", registry_url)
            except: pass

        try:
            ctx = ssl._create_unverified_context()
            req = urllib.request.Request(registry_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10, context=ctx) as response:
                remote_data = json.loads(response.read().decode("utf-8"))
                remote_models = remote_data.get("models", [])
                for rm in remote_models:
                    # Convert dict to ModelMetadata for consistency
                    new_models.append(heuristic_classify(rm["id"], rm.get("family", "custom")))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return False, f"Sync failed: Registry not found at {registry_url}."
            return False, f"Sync failed: HTTP Error {e.code}"
        except Exception as e:
            return False, f"Sync failed: {e}"

    if not new_models:
        return False, f"No models found from {source_name}."
            
    # Load current global custom models to merge
    current_custom = {"models": []}
    if global_config.exists():
        try:
            current_custom = json.loads(global_config.read_text(encoding="utf-8"))
        except: pass
        
    # Merge logic
    merged_map = {m["id"]: m for m in current_custom.get("models", [])}
    for nm in new_models:
        # Convert ModelMetadata back to dict for JSON storage
        m_dict = {
            "id": nm.id,
            "family": nm.family,
            "tier": nm.tier.name,
            "capabilities": [c.value for c in nm.capabilities],
            "cost_factor": nm.cost_factor,
            "required_clis": nm.required_clis,
            "api_model_id": nm.api_model_id
        }
        merged_map[nm.id] = m_dict
        
    new_data = {"models": sorted(list(merged_map.values()), key=lambda x: x["id"])}
    global_config.write_text(json.dumps(new_data, indent=2), encoding="utf-8")
    
    # Invalidate cache
    global _ALL_MODELS_CACHE
    _ALL_MODELS_CACHE = None
    
    return True, f"Successfully synced {len(new_models)} models from {source_name}."
