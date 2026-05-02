"""User-facing settings — profile + per-agent config.

Persisted to data/jarvis_settings.json. Sensitive fields (none here currently)
would be .gitignored; the whole file is gitignored as a safety measure.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.config import settings as app_settings
from app.jarvis.agents import JARVIS_AGENTS


class Location(BaseModel):
    lat: float = 35.6762
    lng: float = 139.6503
    label: str = "Tokyo"
    timezone: str = "Asia/Tokyo"
    timezone_source: str = "auto"


class SleepSchedule(BaseModel):
    bedtime: str = "23:00"
    wake: str = "07:00"


class UserProfile(BaseModel):
    name: str = ""
    pronouns: str = ""
    occupation: str = ""
    location: Location = Field(default_factory=Location)
    sleep_schedule: SleepSchedule = Field(default_factory=SleepSchedule)
    diet_restrictions: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)


class AgentConfig(BaseModel):
    enabled: bool = True
    interrupt_budget: int = 3


def _default_agent_configs() -> dict[str, AgentConfig]:
    result: dict[str, AgentConfig] = {}
    for agent_id, agent in JARVIS_AGENTS.items():
        if agent_id == "shadow":
            continue
        result[agent_id] = AgentConfig(
            enabled=True,
            interrupt_budget=agent.get("interrupt_budget", 3),
        )
    return result


def _reconcile_agent_configs(settings: "JarvisSettings") -> "JarvisSettings":
    defaults = _default_agent_configs()
    merged = {**defaults, **settings.agents}
    for agent_id, default_config in defaults.items():
        existing = merged.get(agent_id)
        if existing is None:
            merged[agent_id] = default_config
            continue
        merged[agent_id] = AgentConfig(
            enabled=existing.enabled,
            interrupt_budget=existing.interrupt_budget,
        )
    if merged == settings.agents:
        return settings
    return settings.model_copy(update={"agents": merged})


class JarvisSettings(BaseModel):
    profile: UserProfile = Field(default_factory=UserProfile)
    agents: dict[str, AgentConfig] = Field(default_factory=_default_agent_configs)
    shadow_learner_enabled: bool = True
    psychological_tracking_enabled: bool = True


# ── Persistence ──────────────────────────────────────────────

_SETTINGS_FILE = Path(app_settings.data_dir) / "jarvis_settings.json"


def _load() -> JarvisSettings:
    if _SETTINGS_FILE.exists():
        try:
            with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            loaded = _reconcile_agent_configs(JarvisSettings.model_validate(data))
            _save(loaded)
            return loaded
        except (json.JSONDecodeError, Exception):
            pass
    return _reconcile_agent_configs(JarvisSettings())


def _save(settings: JarvisSettings) -> None:
    _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings.model_dump(), f, ensure_ascii=False, indent=2)


# Singleton cached
_cached: JarvisSettings | None = None


def get_settings() -> JarvisSettings:
    global _cached
    if _cached is None:
        _cached = _load()
    return _cached


def update_profile(patch: dict[str, Any]) -> JarvisSettings:
    current = get_settings()
    new_profile = current.profile.model_copy(update={})
    for key, value in patch.items():
        if hasattr(new_profile, key) and value is not None:
            # For nested models accept dict patch
            current_attr = getattr(new_profile, key)
            if isinstance(current_attr, BaseModel) and isinstance(value, dict):
                if key == "location" and value.get("timezone"):
                    value = {**value, "timezone_source": value.get("timezone_source") or "manual"}
                setattr(new_profile, key, current_attr.model_copy(update=value))
            else:
                setattr(new_profile, key, value)
    new_settings = current.model_copy(update={"profile": new_profile})
    _save(new_settings)
    global _cached
    _cached = new_settings
    return new_settings


def update_agent_config(agent_id: str, patch: dict[str, Any]) -> JarvisSettings:
    current = get_settings()
    agents = {**current.agents}
    existing = agents.get(agent_id, AgentConfig())
    agents[agent_id] = existing.model_copy(update=patch)
    new_settings = current.model_copy(update={"agents": agents})
    _save(new_settings)
    global _cached
    _cached = new_settings
    return new_settings


def update_shadow_enabled(enabled: bool) -> JarvisSettings:
    current = get_settings()
    new_settings = current.model_copy(update={"shadow_learner_enabled": enabled})
    _save(new_settings)
    global _cached
    _cached = new_settings
    return new_settings


def update_psychological_tracking_enabled(enabled: bool) -> JarvisSettings:
    current = get_settings()
    new_settings = current.model_copy(update={"psychological_tracking_enabled": enabled})
    _save(new_settings)
    global _cached
    _cached = new_settings
    return new_settings


def is_psychological_tracking_enabled() -> bool:
    return bool(get_settings().psychological_tracking_enabled)


def build_profile_prefix() -> str:
    """Build a prompt prefix describing the user. Returns '' if profile is empty.

    A profile is considered "empty" when the user has not provided any
    identifying text fields (name/pronouns/occupation/interests/diet).
    In that case we skip the prefix entirely — default Location/SleepSchedule
    values alone are not enough to synthesise a user profile.
    """
    profile = get_settings().profile
    has_identity = bool(
        profile.name
        or profile.pronouns
        or profile.occupation
        or profile.interests
        or profile.diet_restrictions
    )
    if not has_identity:
        return ""
    parts: list[str] = []
    if profile.name:
        parts.append(f"用户称呼: {profile.name}")
    if profile.pronouns:
        parts.append(f"代词: {profile.pronouns}")
    if profile.occupation:
        parts.append(f"职业: {profile.occupation}")
    if profile.location and profile.location.label:
        parts.append(f"位置: {profile.location.label}")
    if profile.interests:
        parts.append(f"兴趣爱好: {', '.join(profile.interests)}")
    if profile.diet_restrictions:
        parts.append(f"饮食限制: {', '.join(profile.diet_restrictions)}")
    if profile.sleep_schedule:
        parts.append(
            f"作息: {profile.sleep_schedule.bedtime} 就寝 / "
            f"{profile.sleep_schedule.wake} 起床"
        )
    if not parts:
        return ""
    return "[用户画像] " + " | ".join(parts) + "\n\n"


def get_enabled_agents(candidate_ids: list[str]) -> list[str]:
    """Filter the candidate list to only agents that are enabled."""
    cfg = get_settings().agents
    return [aid for aid in candidate_ids if cfg.get(aid, AgentConfig()).enabled]
