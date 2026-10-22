"""Embedded Assistant sessions with short-lived API credentials held in memory only.

A new runtime session ends the previous active session of the same delegation.
Session identity and registry pins are retained; cookie and CSRF values are not.
"""

from dataclasses import dataclass
import time

from ..agent_tools.registry import PLAYBOOK_SHA256, REGISTRY_VERSION
from ..contracts import DomainError, uid
from . import control, limits, records
from .delegations import iso
from .schema import SURFACES

CLIENT_DISPLAY_NAMES = {'hyprn-claude-managed': 'Assistant'}
DEFAULT_DISPLAY_NAME = 'Assistant'
MAX_CLIENT_TEXT = 64

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

    def open(self, grant, client_info, *, surface):
        """Open a session for a server-created delegation, never an external credential."""
        if not control.agent_enabled(self._environ):
            raise SessionRefused('agent_disabled')
        if surface not in SURFACES or grant.get('surface') != surface:
            raise SessionRefused('access_lost')
        try:
            api_session = self._auth.mint_agent_session(grant['delegation_id'])
        except DomainError:
            raise SessionRefused('access_lost') from None
        info = client_info if isinstance(client_info, dict) else {}
        now = iso(self._clock())
        row = dict(
            session_id=uid(),
            delegation_id=grant['delegation_id'],
            surface=surface,
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
            ended = records.end_delegation_sessions(db, row['delegation_id'], now)
            records.insert_session(db, row)
        for session_id in ended:
            self._api.pop(session_id, None)
        self._api[row['session_id']] = api_session
        return SessionHandle(
            session_id=row['session_id'],
            surface=surface,
            study_id=api_session['study_id'],
            agent_display_name=row['agent_display_name'],
        )

    def get(self, session_id):
        """The stored session ``session_id``; ``None`` when there is none."""
        with self._store.connection() as db:
            return records.session(db, session_id)

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
