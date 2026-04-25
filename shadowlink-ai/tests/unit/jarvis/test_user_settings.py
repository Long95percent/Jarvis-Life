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
