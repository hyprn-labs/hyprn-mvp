"""Agent sessions: one per surface session, bound to one delegation, with its delegated API
session held in memory only.

Opening a session for a tool token ends every earlier session of that token (one MCP session
per token, so a restarted relay never locks the user out). The display name stored on the
session comes from a closed mapping of reported client names; client text never becomes a
record name. The client's reported name and version are informational, kept only when they are
short printable text. The delegated API session (``Auth.mint_agent_session``, 15 minutes) is
re-minted before it expires; its cookie and cross-site request values stay in this object's
memory, are never stored, logged or returned in a representation, and leave with the session.
"""

from dataclasses import dataclass
import re
import time

from ..agent_tools.registry import PLAYBOOK_SHA256, REGISTRY_VERSION
from ..contracts import DomainError, uid
from . import control, limits, records
from .delegations import LOCAL_AGENT_NAME, LOCAL_SURFACE, iso

# Reported client names (MCP ``clientInfo.name``, exact match) and the display name stored for
# them; any other name gets the default.
CLIENT_DISPLAY_NAMES = {
    'claude-code': 'Claude Code (local)',
    'codex-mcp-client': 'Codex (local)',
}
DEFAULT_DISPLAY_NAME = LOCAL_AGENT_NAME
MAX_CLIENT_TEXT = 64
SURFACE_SESSION_ID = re.compile(r'[\x21-\x7e]{1,128}')
PROTOCOL_VERSION = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}')


class SessionRefused(Exception):
    """A session cannot open or continue; ``reason`` is ``agent_disabled`` or
    ``access_lost``."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class SessionHandle:
    """What a surface keeps for an open agent session; it carries no credential."""

    session_id: str
    surface: str
    mcp_session_id: str | None
    study_id: str
    agent_display_name: str


def client_text(value):
    """``value`` when it is 1 to 64 printable characters, otherwise ``None``."""
    if isinstance(value, str) and 0 < len(value) <= MAX_CLIENT_TEXT and value.isprintable():
        return value
    return None


def display_name(client_info):
    """The display name for a reported client, from the closed mapping."""
    name = client_info.get('name') if isinstance(client_info, dict) else None
    return (
        CLIENT_DISPLAY_NAMES.get(name, DEFAULT_DISPLAY_NAME)
        if isinstance(name, str)
        else (DEFAULT_DISPLAY_NAME)
    )


class Sessions:
    """The agent sessions of one installation process."""

    def __init__(self, store, auth, registry, environ, *, clock=time.time):
        self._store, self._auth, self._registry = store, auth, registry
        self._environ, self._clock = environ, clock
        self._api = {}

    def __repr__(self):
        return 'Sessions()'

    def open(self, grant, mcp_session_id, client_info, protocol_version, *, surface=LOCAL_SURFACE):
        """Open an agent session for ``grant`` (``Auth.verify_tool_token``'s result: the
        delegation, its study and the token). Refused while agent access is off for the
        installation (``agent_disabled``) and when the delegation is no longer live
        (``access_lost``). Ends every earlier active session of the same token."""
        if not control.agent_enabled(self._environ):
            raise SessionRefused('agent_disabled')
        if mcp_session_id is not None and not (
            isinstance(mcp_session_id, str) and SURFACE_SESSION_ID.fullmatch(mcp_session_id)
        ):
            raise ValueError('A surface session id is 1 to 128 visible ASCII characters')
        if protocol_version is not None and not (
            isinstance(protocol_version, str) and PROTOCOL_VERSION.fullmatch(protocol_version)
        ):
            raise ValueError('A protocol version is a dated revision')
        try:
            api_session = self._auth.mint_agent_session(grant['delegation_id'])
        except DomainError:
            raise SessionRefused('access_lost') from None
        info = client_info if isinstance(client_info, dict) else {}
        now = iso(self._clock())
        row = dict(
            session_id=uid(),
            delegation_id=grant['delegation_id'],
            token_id=grant.get('token_id'),
            surface=surface,
            mcp_session_id=mcp_session_id,
            protocol_version=protocol_version,
            client_name=client_text(info.get('name')),
            client_version=client_text(info.get('version')),
            agent_display_name=display_name(info),
            registry_version=REGISTRY_VERSION,
            playbook_sha256=PLAYBOOK_SHA256,
            tool_definitions_sha256=self._registry.definitions_sha256(),
            state='active',
            api_calls=0,
            runs_submitted=0,
            started_at=now,
            ended_at=None,
        )
        with self._store.connection(write=True) as db:
            ended = []
            if row['token_id'] is not None:
                ended = records.end_token_sessions(db, row['token_id'], now)
            records.insert_session(db, row)
        for session_id in ended:
            self._api.pop(session_id, None)
        self._api[row['session_id']] = api_session
        return SessionHandle(
            session_id=row['session_id'],
            surface=surface,
            mcp_session_id=mcp_session_id,
            study_id=api_session['study_id'],
            agent_display_name=row['agent_display_name'],
        )

    def get(self, session_id):
        """The stored session ``session_id``; ``None`` when there is none."""
        with self._store.connection() as db:
            return records.session(db, session_id)

    def by_surface_id(self, mcp_session_id):
        """The stored session of surface session id ``mcp_session_id``; ``None`` when none."""
        with self._store.connection() as db:
            return records.session_by_surface_id(db, mcp_session_id)

    def end(self, session_id, state='ended'):
        """End session ``session_id`` (``ended``, or ``access_lost``, which is sticky) and
        drop its API session. Whether it was active."""
        if state not in ('ended', 'access_lost'):
            raise ValueError('A session ends as ended or access_lost')
        self._api.pop(session_id, None)
        with self._store.connection(write=True) as db:
            return records.end_session(db, session_id, state, iso(self._clock()))

    def api_session(self, session_id, delegation_id):
        """The delegated API session of ``session_id`` with at least a minute left, re-minted
        when needed. Raises ``SessionRefused('access_lost')`` when the delegation is no longer
        live. The returned mapping holds the cookie and cross-site request values; callers
        pass it only to the in-process API client."""
        current = self._api.get(session_id)
        if current is not None:
            remaining = current['expires_at'] - self._clock()
            if remaining > limits.API_SESSION_MARGIN_SECONDS:
                return current
        try:
            current = self._auth.mint_agent_session(delegation_id)
        except DomainError:
            self._api.pop(session_id, None)
            raise SessionRefused('access_lost') from None
        self._api[session_id] = current
        return current

    def live(self, session_id, delegation_id):
        """The delegated API session of ``session_id`` after ``Auth.authenticate`` confirmed
        that it and its delegation are live (one re-mint when the API session itself lapsed);
        with the delegation's ``effects`` and agent ``actor_id``. Raises
        ``SessionRefused('access_lost')`` otherwise."""
        for _ in range(2):
            current = self.api_session(session_id, delegation_id)
            try:
                checked = self._auth.authenticate(current['token'])
            except DomainError:
                self._api.pop(session_id, None)
                continue
            if checked.get('delegation_id') != delegation_id:
                break
            return current, checked
        raise SessionRefused('access_lost')
