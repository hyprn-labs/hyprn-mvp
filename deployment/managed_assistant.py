"""Release-bound Claude resource setup, with no session or scientific execution.

Run with the locked application environment: python -m deployment.managed_assistant.
Plan is offline. Apply requires the reviewed digest; reconcile performs GETs only.
The private journal is the single writer's durable record of attempted creations.
"""

import argparse
import asyncio
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

from hyprn_mvp_app.agent_runtime.delegations import ROLE_EFFECTS
from hyprn_mvp_app.agent_tools import catalogue, playbook
from hyprn_mvp_app.agent_tools.registry import LOCAL_STAGE, Registry
from hyprn_mvp_app.assistant.claude import (
    Claude,
    ProviderError,
    agent_definition,
    credential,
    identity,
)
from hyprn_mvp_app.contracts import digest
from hyprn_mvp_app.locations import location_refusal

REPO = Path(__file__).resolve().parents[1]
MODELS = ('claude-haiku-5-5', 'claude-sonnet-5-5', 'claude-opus-5-5')
MANAGERS = ('apt', 'cargo', 'gem', 'go', 'npm', 'pip')
PREFIX = 'HYPRN_MVP_ASSISTANT_'


def definition(deployment, model, effort):
    """Derive actual wire payloads; there is no second tool or playbook registry."""
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,47}', deployment) or model not in MODELS:
        raise ProviderError('definition_invalid')
    if effort not in ('low', 'medium', 'high'):
        raise ProviderError('definition_invalid')
    tools = Registry(catalogue.TOOLS).definitions(
        'claude_managed', LOCAL_STAGE, ROLE_EFFECTS['writer']
    )
    guidance = playbook.render_document()
    system = (
        'You are the HYPRN study assistant. Follow the release playbook below and load '
        'get_playbook guidance for each operation. Use only the offered HYPRN custom tools. '
        'Delegate bounded subtasks within this study using the same tools and shared allowance. '
        'Run candidate scientific code only through the attested HYPRN execution boundary.\n\n'
        + guidance
    )
    agent = agent_definition(
        {'id': model, 'effort': {'type': effort}, 'speed': 'standard'},
        tools,
        system,
    )
    agent.update(mcp_servers=[], skills=[])
    agent['multiagent']['subagents']['predefined_agents'] = []
    environment = {
        'config': {
            'type': 'cloud',
            'networking': {
                'type': 'limited',
                'allowed_hosts': [],
                'allow_mcp_servers': False,
                'allow_package_managers': False,
            },
        }
    }
    value = {
        'schema_version': 1,
        'deployment': deployment,
        'definitions_sha256': digest(tools),
        'playbook_sha256': digest(guidance),
        'agent': agent,
        'environment': environment,
    }
    value['configuration_sha256'] = digest(value)
    for kind in ('agent', 'environment'):
        resource_hash = digest(value[kind])
        value[kind]['name'] = 'hyprn-' + deployment + '-' + kind + '-' + resource_hash[:20]
        value[kind]['metadata'] = {
            'hyprn_deployment': deployment,
            'hyprn_definition_sha256': resource_hash,
        }
    return value


def private_path(value):
    path = Path(value)
    if location_refusal(path) or path.resolve().is_relative_to(REPO):
        raise ProviderError('private_path_required')
    if not path.parent.is_dir():
        raise ProviderError('private_directory_required')
    parent = path.parent.stat()
    if parent.st_uid != os.getuid() or stat.S_IMODE(parent.st_mode) & 0o022:
        raise ProviderError('private_directory_required')
    if path.exists():
        info = path.stat()
        if (
            not stat.S_ISREG(info.st_mode)
            or stat.S_IMODE(info.st_mode) & 0o077
            or info.st_uid != os.getuid()
        ):
            raise ProviderError('private_file_required')
    return path


def read_json(path):
    try:
        with path.open() as stream:
            raw = stream.read(4 * 1024 * 1024 + 1)
        if len(raw) > 4 * 1024 * 1024:
            raise ValueError()
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (OSError, ValueError):
        raise ProviderError('state_or_plan_invalid') from None


def save(path, value):
    """Atomic owner-only state replacement, fsynced before the next provider effect."""
    fd, temporary = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def locked(path):
    lock = private_path(str(path) + '.lock')
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ProviderError('setup_already_running') from None
        yield
    finally:
        os.close(fd)


def checked_plan(path):
    value = read_json(path)
    try:
        model = value['agent']['model']
        current = definition(value['deployment'], model['id'], model['effort']['type'])
    except (KeyError, TypeError):
        raise ProviderError('definition_invalid') from None
    if value != current:
        raise ProviderError('release_definition_changed')
    return value


def matches(record, desired, kind):
    """Compare controlled fields, rejecting added execution capabilities."""
    if record.get('archived_at') is not None:
        return False
    if kind == 'environment':
        # Do not specify packages at creation: the API requires registry network access
        # when packages are specified. Its empty default is checked explicitly on reads.
        desired = {
            **desired,
            'config': {
                **desired['config'],
                'packages': {'type': 'packages', **{manager: [] for manager in MANAGERS}},
            },
        }
    return all(record.get(key) == expected for key, expected in desired.items())


async def find(provider, kind, desired):
    matches_metadata, cursor, seen = [], None, set()
    for _ in range(100):
        params = {'limit': 100, 'include_archived': 'true'}
        if cursor:
            params['page'] = cursor
        page = await provider.request('GET', '/v1/' + kind + 's', params=params)
        if not isinstance(page.get('data'), list):
            raise ProviderError('invalid_provider_record')
        for record in page['data']:
            if not isinstance(record, dict):
                raise ProviderError('invalid_provider_record')
            if record.get('metadata') == desired['metadata']:
                matches_metadata.append(record)
        cursor = page.get('next_page')
        if cursor is None:
            break
        if not isinstance(cursor, str) or not cursor or cursor in seen:
            raise ProviderError('invalid_provider_record')
        seen.add(cursor)
    else:
        raise ProviderError('provider_listing_incomplete')
    if len(matches_metadata) > 1:
        raise ProviderError('ambiguous_resource')
    return matches_metadata[0] if matches_metadata else None


async def readback(provider, kind, record, desired):
    resource_id = identity(record.get('id'))
    params = None
    if kind == 'agent':
        version = record.get('version')
        if type(version) is not int or version < 1:
            raise ProviderError('invalid_provider_record')
        params = {'version': version}
    actual = await provider.request('GET', '/v1/' + kind + 's/' + resource_id, params=params)
    if (
        actual.get('id') != resource_id
        or not matches(actual, desired, kind)
        or (kind == 'agent' and actual.get('version') != version)
    ):
        raise ProviderError('provider_definition_drift')
    return {'id': resource_id, **({'version': version} if kind == 'agent' else {})}


async def provision(plan, state_path, key_file, *, mutate, transport):
    credential(key_file)  # Reject unavailable credentials before recording a creation intent.
    provider = Claude(key_file, transport=transport)
    try:
        with locked(state_path):
            state = (
                read_json(state_path)
                if state_path.exists()
                else {'schema_version': 1, 'resources': {}}
            )
            if (
                set(state) != {'schema_version', 'resources'}
                or state['schema_version'] != 1
                or not isinstance(state['resources'], dict)
            ):
                raise ProviderError('state_or_plan_invalid')
            bindings = {}
            for kind in ('environment', 'agent'):
                desired = plan[kind]
                intent_key = kind + ':' + digest(desired)
                saved = state['resources'].get(intent_key)
                if saved and saved.get('status') == 'confirmed':
                    found = saved['binding']
                else:
                    found = await find(provider, kind, desired)
                if found is None:
                    if saved and saved.get('status') != 'rejected':
                        raise ProviderError('creation_uncertain_requires_reconciliation')
                    if not mutate:
                        raise ProviderError('setup_incomplete')
                    state['resources'][intent_key] = {'status': 'intent'}
                    save(state_path, state)
                    # A timeout or crash leaves the intent. Definitive rejection permits
                    # a later explicit apply, but never a retry in this invocation.
                    try:
                        found = await provider.request('POST', '/v1/' + kind + 's', body=desired)
                    except ProviderError as error:
                        if not error.uncertain:
                            state['resources'][intent_key] = {'status': 'rejected'}
                            save(state_path, state)
                        raise
                binding = await readback(provider, kind, found, desired)
                state['resources'][intent_key] = {'status': 'confirmed', 'binding': binding}
                save(state_path, state)
                bindings[kind] = binding
            # Environments are mutable: confirm both resources again at export time.
            for kind in ('environment', 'agent'):
                await readback(provider, kind, bindings[kind], plan[kind])
            return {
                PREFIX + 'AGENT_ID': bindings['agent']['id'],
                PREFIX + 'AGENT_VERSION': str(bindings['agent']['version']),
                PREFIX + 'ENVIRONMENT_ID': bindings['environment']['id'],
                PREFIX + 'DEFINITIONS_SHA256': plan['definitions_sha256'],
                PREFIX + 'CONFIGURATION_SHA256': plan['configuration_sha256'],
            }
    finally:
        await provider.close()


def main(argv=None, *, transport=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('plan', 'apply', 'reconcile'))
    parser.add_argument('--plan', required=True)
    parser.add_argument('--deployment')
    parser.add_argument('--model', choices=MODELS)
    parser.add_argument('--effort', choices=('low', 'medium', 'high'))
    parser.add_argument('--state')
    parser.add_argument('--key-file', default=os.environ.get(PREFIX + 'KEY_FILE'))
    parser.add_argument('--approve')
    args = parser.parse_args(argv)
    try:
        plan_path = private_path(args.plan)
        if args.command == 'plan':
            if not all((args.deployment, args.model, args.effort)):
                raise ProviderError('explicit_definition_required')
            plan = definition(args.deployment, args.model, args.effort)
            if plan_path.exists() and read_json(plan_path) != plan:
                raise ProviderError('plan_already_exists')
            save(plan_path, plan)
            print(json.dumps({'configuration_sha256': plan['configuration_sha256']}))
            return 0
        plan = checked_plan(plan_path)
        if args.command == 'apply' and args.approve != plan['configuration_sha256']:
            raise ProviderError('reviewed_digest_required')
        if not args.state or not args.key_file:
            raise ProviderError('private_state_and_key_file_required')
        state_path, key_file = private_path(args.state), private_path(args.key_file)
        paths = (plan_path, state_path, key_file, Path(str(state_path) + '.lock'))
        if len({str(path) for path in paths}) != len(paths):
            raise ProviderError('paths_must_be_distinct')
        result = asyncio.run(
            provision(
                plan,
                state_path,
                key_file,
                mutate=args.command == 'apply',
                transport=transport,
            )
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except ProviderError as error:
        print(json.dumps({'error': error.code}), file=sys.stderr)
        return 2
    except (OSError, ValueError, KeyError, TypeError):
        print(json.dumps({'error': 'setup_state_invalid'}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
