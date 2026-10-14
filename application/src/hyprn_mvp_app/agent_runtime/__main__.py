"""Operator commands for local agent access. This module deliberately has no HTTP route.

    python -m hyprn_mvp_app.agent_runtime mint-token --store PATH --study ID --owner USERNAME
        [--ttl-hours N] [--client-label TEXT]
    python -m hyprn_mvp_app.agent_runtime list-tokens --store PATH --study ID
    python -m hyprn_mvp_app.agent_runtime revoke --store PATH --study ID [--token-id ID]

``mint-token`` writes the new token once to standard output and nothing else there; the
caller (the local edition's command line) keeps it in the operating system's credential
store. ``list-tokens`` and ``revoke`` print JSON without any secret. No secret is ever accepted
as an argument, and nothing here logs a token.
"""

import argparse
import json
import sys

from ..auth import Auth
from ..contracts import DomainError
from ..store import Store
from . import schema, tokens


def parser():
    commands = argparse.ArgumentParser(
        prog='python -m hyprn_mvp_app.agent_runtime',
        description='Local agent access: mint, list and revoke study tool tokens.',
    )
    actions = commands.add_subparsers(dest='action', required=True)
    mint = actions.add_parser('mint-token', help='Mint a study tool token (printed once).')
    listing = actions.add_parser('list-tokens', help="List the study's tool tokens (no secrets).")
    revoke = actions.add_parser('revoke', help='Revoke a study tool token, or all of them.')
    for action in (mint, listing, revoke):
        action.add_argument('--store', required=True)
        action.add_argument('--study', required=True)
    mint.add_argument('--owner', required=True)
    mint.add_argument('--ttl-hours', type=int, default=tokens.DEFAULT_TTL_HOURS)
    mint.add_argument('--client-label', default='local')
    revoke.add_argument('--token-id')
    return commands


def main(argv=None, environ=None):
    args = parser().parse_args(argv)
    store = Store(args.store)
    schema.ensure(store)
    try:
        if args.action == 'mint-token':
            _, token = tokens.mint_local(
                store,
                Auth(store, ''),
                args.owner,
                args.study,
                ttl_hours=args.ttl_hours,
                client_label=args.client_label,
                environ=environ,
            )
            sys.stdout.write(token + '\n')
        elif args.action == 'list-tokens':
            print(json.dumps(tokens.list_for_study(store, args.study), indent=2))
        else:
            revoked = tokens.revoke(store, args.study, args.token_id)
            print(json.dumps(dict(revoked=revoked), indent=2))
    except DomainError as error:
        # The error code only: never an argument value or a secret.
        print(f'Refused: {error.code}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
