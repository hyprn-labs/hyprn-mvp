"""Read-only startup reconciliation; no unknown provider usage becomes zero."""

import asyncio
import re
import time

from hyprn_mvp_app.assistant.claude import ProviderError, Settings, identity
from .runtime import host_record, required


async def reconcile(store, provider, settings, plan, continuity, expected_identity):
    from managed_assistant import readback, validate_plan, verify_bindings
    if plan.get('stage') != 'bound':
        raise ProviderError('exact_bootstrap_bindings_required')
    validate_plan(plan)
    if (plan['definitions_sha256'] != settings.definitions_sha256
            or set(continuity) != {'schema', *expected_identity, 'configuration_sha256',
                                  'prior_cents', 'total_cents', 'carried_sessions', 'review_sha256',
                                  'untracked_cents'}
            or continuity['schema'] != 'hyprn-assistant-continuity/v1'
            or any(continuity[k] != v for k, v in expected_identity.items())
            or continuity['configuration_sha256'] != plan['configuration_sha256']
            or type(continuity['prior_cents']) is not int
            or type(continuity['total_cents']) is not int
            or continuity['prior_cents'] != settings.prior_cents
            or continuity['total_cents'] != settings.total_cents):
        raise ProviderError('shared_allowance_unknown')
    if not isinstance(continuity['review_sha256'], str) or not re.fullmatch('[0-9a-f]{64}', continuity['review_sha256']):
        raise ProviderError('shared_allowance_unknown')
    await verify_bindings(provider, plan)
    await readback(provider, 'agent', {'id': settings.agent_id, 'version': settings.agent_version},
                   plan['agent'])
    await readback(provider, 'environment', {'id': settings.environment_id}, plan['environment'])
    carried = continuity['carried_sessions']
    if not isinstance(carried, dict) or any(type(v) is not int or v < 0 for v in carried.values()):
        raise ProviderError('shared_allowance_unknown')
    for session_id in carried:
        identity(session_id)
    if (type(continuity['untracked_cents']) is not int or continuity['untracked_cents'] < 0
            or sum(carried.values()) + continuity['untracked_cents'] != settings.prior_cents):
        raise ProviderError('shared_allowance_unknown')
    known = {}
    # Each retained provider generation has its own immutable correlation key.
    # The current conversation pointer is not an inventory of historical usage.
    for row in store.assistant_user_accounts():
        if not row['provider_id'] and row['provision'] == 'new':
            continue
        found = await provider.find_session(row['conversation_id'])
        if not found or (row['provider_id'] and row['provider_id'] != found.get('id')):
            raise ProviderError('shared_allowance_unknown')
        session_id = identity(found['id'])
        if session_id in known or session_id in carried:
            raise ProviderError('shared_allowance_unknown')
        known[session_id] = None
    # Enumerate the entire credential-visible inventory. An unclassified session
    # requires an explicit review, including sessions absent from a restored store.
    visible, cursor, cursors = set(), None, set()
    for _ in range(100):
        page = await provider.request('GET', '/v1/sessions',
                                      params={'limit': 100, 'include_archived': 'true',
                                              **({'page': cursor} if cursor else {})})
        if not isinstance(page.get('data'), list):
            raise ProviderError('shared_allowance_unknown')
        for row in page['data']:
            session_id = identity(row.get('id'))
            if session_id in visible:
                raise ProviderError('ambiguous_provider_record')
            visible.add(session_id)
        cursor = page.get('next_page')
        if cursor is None:
            break
        if not isinstance(cursor, str) or not cursor or cursor in cursors:
            raise ProviderError('shared_allowance_unknown')
        cursors.add(cursor)
    else:
        raise ProviderError('provider_history_limit')
    if visible != set(known) | set(carried):
        raise ProviderError('shared_allowance_unknown')
    spent = continuity['untracked_cents']
    for session_id in sorted(visible):
        account = await provider.session_account(session_id)
        if account['status'] not in ('idle', 'terminated'):
            raise ProviderError('shared_allowance_busy')
        if session_id in carried and account['spent_cents'] != carried[session_id]:
            raise ProviderError('shared_allowance_unknown')
        spent += account['spent_cents']
    # Legacy installation totals remain reconciliation evidence. Admission now
    # uses cumulative per-user study usage; startup does not impose a global cap.
    return {'reconciled_at': int(time.time()), 'spent_cents': spent, 'sessions': len(visible)}


def install(app, environ):
    # Missing PRIOR_CENTS must not inherit the local adapter's zero default.
    required(environ, 'ASSISTANT_PRIOR_CENTS')
    settings = Settings.from_environment(environ)
    if settings is None:
        raise ValueError('Hosted configuration requires the embedded Assistant')
    plan = host_record(required(environ, 'ASSISTANT_PLAN_FILE'), max_bytes=1024 * 1024)
    continuity = host_record(required(environ, 'ASSISTANT_CONTINUITY_FILE'))
    if plan.get('configuration_sha256') != required(environ, 'ASSISTANT_CONFIGURATION_SHA256'):
        raise ValueError('Hosted configuration Assistant definition differs')

    async def checked_start():
        app.state.assistant_startup = await asyncio.wait_for(reconcile(
            app.state.store, app.state.assistant.provider, settings, plan, continuity,
            app.state.admission.identity), timeout=90)
        app.state.assistant.configure_reviewers(plan['bindings']['reviewers'], plan['review_limits'])

    # Validate before the existing delivery pump is allowed to recover accepted work.
    app.router.on_startup.insert(0, checked_start)
