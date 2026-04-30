import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from app.jarvis.user_settings import (
    JarvisSettings,
    UserProfile,
    AgentConfig,
    build_profile_prefix,
    get_enabled_agents,
)


def test_empty_profile_prefix_is_empty():
    # Patch settings cache to return empty profile
    with patch("app.jarvis.user_settings._cached", JarvisSettings()):
        assert build_profile_prefix() == ""


def test_profile_prefix_includes_name():
    s = JarvisSettings(profile=UserProfile(name="Motoki", occupation="学生"))
    with patch("app.jarvis.user_settings._cached", s):
        prefix = build_profile_prefix()
        assert "Motoki" in prefix
        assert "学生" in prefix
        assert "用户画像" in prefix


def test_disabled_agent_filtered_out():
    s = JarvisSettings(
        agents={
            "alfred": AgentConfig(enabled=True),
            "nora": AgentConfig(enabled=False),
            "mira": AgentConfig(enabled=True),
        }
    )
    with patch("app.jarvis.user_settings._cached", s):
        result = get_enabled_agents(["alfred", "nora", "mira"])
        assert result == ["alfred", "mira"]


def test_settings_load_reconciles_new_agents(monkeypatch, tmp_path):
    import json
    import app.jarvis.user_settings as user_settings

    settings_file = tmp_path / "jarvis_settings.json"
    settings_file.write_text(
        json.dumps(
            {
                "profile": {},
                "agents": {
                    "alfred": {"enabled": True, "interrupt_budget": 3},
                    "maxwell": {"enabled": True, "interrupt_budget": 5},
                },
                "shadow_learner_enabled": True,
                "psychological_tracking_enabled": True,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(user_settings, "_SETTINGS_FILE", settings_file)
    monkeypatch.setattr(user_settings, "_cached", None)

    settings = user_settings.get_settings()

    assert "athena" in settings.agents
    assert settings.agents["athena"].enabled is True
    assert settings.agents["athena"].interrupt_budget >= 1


def test_settings_load_preserves_explicit_zero_interrupt_budget(monkeypatch, tmp_path):
    import json
    import app.jarvis.user_settings as user_settings

    settings_file = tmp_path / "jarvis_settings.json"
    settings_file.write_text(
        json.dumps(
            {
                "profile": {},
                "agents": {
                    "athena": {"enabled": True, "interrupt_budget": 0},
                    "maxwell": {"enabled": True, "interrupt_budget": 0},
                },
                "shadow_learner_enabled": True,
                "psychological_tracking_enabled": True,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(user_settings, "_SETTINGS_FILE", settings_file)
    monkeypatch.setattr(user_settings, "_cached", None)

    settings = user_settings.get_settings()

    assert settings.agents["athena"].interrupt_budget == 0
    assert settings.agents["maxwell"].interrupt_budget == 0
