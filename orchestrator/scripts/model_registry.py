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

# Legacy / Base IDs from llm.py that we should support as aliases or direct lookups
LEGACY_IDS = {
    "gemini": "gemini-3.1-pro-preview",
    "claude": "claude-sonnet-4-6",
    "codex": "gpt-5.4",
    "opencode": "opencode/big-pickle",
}

def get_model(model_id: str) -> ModelMetadata | None:
    # Check ID and aliases
    for m in MODELS:
        if model_id == m.id or model_id in m.aliases:
            return m
    return None

def get_all_models() -> list[ModelMetadata]:
    return MODELS
