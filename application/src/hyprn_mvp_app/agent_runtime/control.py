"""The installation kill switch for agent access (fail closed)."""

AGENT_ENABLED = 'HYPRN_MVP_AGENT_ENABLED'


def agent_enabled(environ):
    """True only when ``HYPRN_MVP_AGENT_ENABLED`` is exactly ``true``; an absent variable or any
    other value is disabled."""
    return environ.get(AGENT_ENABLED) == 'true'
