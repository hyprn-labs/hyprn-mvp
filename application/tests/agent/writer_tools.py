"""A fresh synthetic study with a writer and a reader agent delegation, for the write tools.

Every tool call goes through the real application, its middleware and the agent route
allowlist, with the delegated agent API session of the chosen delegation. ``attributed`` reads
the attribution entries the owners recorded, as a member sees them.
"""

import asyncio
import time
from uuid import uuid4

from conftest import LOOPBACK_ORIGIN
from hyprn_mvp_app.agent_runtime import attribution
from hyprn_mvp_app.agent_tools.api_client import ApiClient
from hyprn_mvp_app.agent_tools.registry import LOCAL_STAGE, REGISTRY
from hyprn_mvp_app.agent_tools.spec import ToolContext, ToolError
from hyprn_mvp_app.contracts import DomainError

WRITER = frozenset({'read', 'draft', 'record', 'submit', 'outside_study'})
READER = frozenset({'read', 'outside_study'})
AGENT_NAME = 'Coding agent (local)'


def uid():
    return str(uuid4())


class NoModeling:
    """The modeling double of tools that never reach the modeling service."""

    def call(self, *_, **__):
        raise DomainError('backend_unavailable', 503, outcome='unknown')


def writer_study(tmp_path, modeling=None, name='Hypersonic fuel choice'):
    from hyprn_mvp_app.api import create_app
    from hyprn_mvp_app.auth import Auth
    from hyprn_mvp_app.store import Store

    store = Store(tmp_path / 'writer-tools.sqlite')
    auth = Auth(store, LOOPBACK_ORIGIN)
    owner = uid()
    with store.connection(write=True) as db:
        db.execute(
            'INSERT INTO users(actor_id,username,password_hash) VALUES(?,?,?)',
            (owner, 'owner', 'unused'),
        )
    app = create_app(store, auth, modeling or NoModeling())
    sid = store.create_study(owner, uid(), name)['study_id']
    delegations = {}
    with store.connection(write=True) as db:
        # One live delegation per agent and study: the reader is a second agent principal.
        agent = store.ensure_agent_actor(db, owner, 'claude_managed', AGENT_NAME)
        other = store.ensure_agent_actor(db, owner, 'openai_agents', 'Coding agent (remote)')
        for who, ceiling, effects in ((agent, 'writer', WRITER), (other, 'reader', READER)):
            delegation = store.create_delegation(
                db, who, sid, ceiling, tuple(sorted(effects)), time.time() + 3600
            )
            delegations[ceiling] = delegation['delegation_id']
    return dict(
        app=app,
        store=store,
        auth=auth,
        owner=owner,
        sid=sid,
        agent=agent,
        writer=auth.mint_agent_session(delegations['writer']),
        reader=auth.mint_agent_session(delegations['reader']),
    )


def call(env, steps, effects=WRITER, session='writer'):
    """Run ``(tool, arguments)`` steps in order; each result or ToolError is returned."""

    async def run():
        async with ApiClient(env['app'], LOOPBACK_ORIGIN) as client:
            ctx = ToolContext(
                surface='claude_managed',
                stage=LOCAL_STAGE,
                effects=effects,
                api=client,
                session=env[session],
            )
            out = []
            for name, arguments in steps:
                try:
                    out.append(await REGISTRY.invoke(name, arguments, ctx))
                except ToolError as error:
                    out.append(error)
            return out

    return asyncio.run(run())


def one(env, name, arguments, **options):
    (result,) = call(env, [(name, arguments)], **options)
    return result


def attributed(env, sid=None):
    """The attribution entries of the study as ``(kind, record_id, version_id, category)``,
    each checked to name the writer agent and the owner it acts for."""
    items = attribution.page(env['store'], env['owner'], sid or env['sid'], None, 100)['items']
    for item in items:
        assert item['agent']['actor_id'] == env['agent'], item
        assert item['delegator']['actor_id'] == env['owner'], item
    return {
        (i['record_kind'], i['record_id'], i['version_id'], i['command_category']) for i in items
    }


def offered(effects):
    return {t.name for t in REGISTRY.offered('claude_managed', LOCAL_STAGE, effects)}
