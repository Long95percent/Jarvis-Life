from app.jarvis.models import (
    LifeContext,
    ProactiveMessage,
    RoundtableDecision,
    UserProfile,
)

def test_life_context_defaults():
    ctx = LifeContext()
    assert ctx.stress_level == 0.0
    assert ctx.schedule_density == 0.0
    assert ctx.mood_trend == "neutral"
    assert ctx.free_windows == []

def test_proactive_message_fields():
    msg = ProactiveMessage(
        agent_id="alfred",
        agent_name="Alfred",
        content="Good morning! You have 3 meetings today.",
        trigger="daily_morning",
    )
    assert msg.agent_id == "alfred"
    assert msg.read is False

def test_user_profile_merge():
    profile = UserProfile()
    profile.record_preference("prefers_brief_responses", True)
    assert profile.preferences["prefers_brief_responses"] is True
