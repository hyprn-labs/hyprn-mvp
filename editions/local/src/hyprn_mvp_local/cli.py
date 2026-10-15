"""``./hyprn-mvp`` commands of the local edition.

    ./hyprn-mvp [--json] version
    ./hyprn-mvp dev check <group> [--units-mixed-repair]
    ./hyprn-mvp dev check qualification [--jobs N]
    ./hyprn-mvp dev check --list [--class must-pass|opt-in]

Exit codes: 0 success, 2 invalid input or location, 3 unsupported host, 5 failed
verification or dependency. The test-group runner keeps its own exit codes.
"""
import argparse
import json
import os
import sys
from uuid import uuid4

from hyprn_mvp_local import toolchain


def parser():
    root = argparse.ArgumentParser(prog='hyprn-mvp', description='HYPRN MVP local edition')
    root.add_argument('--json', action='store_true', help='print one JSON document')
    commands = root.add_subparsers(dest='command', required=True, metavar='command')
    commands.add_parser('version', help='print the tool, Python, lock, edition and release identities')
    dev = commands.add_parser('dev', help='developer commands')
    dev_commands = dev.add_subparsers(dest='dev_command', required=True, metavar='command')
    check = dev_commands.add_parser(
        'check', help='run a test group of deployment/checks.py in the locked environments')
    check.add_argument('group', nargs='?', help='a test group, or "qualification" for every must-pass group')
    check.add_argument('--list', action='store_true', help='list every group with its class and environment needs')
    check.add_argument('--class', dest='group_class', choices=('must-pass', 'opt-in'), help='with --list: only this class')
    check.add_argument('--jobs', type=int, metavar='N',
                       help='with qualification: groups run at once (default 3; 1 runs them one after the other)')
    check.add_argument('--units-mixed-repair', action='store_true', help=argparse.SUPPRESS)
    check.add_argument('--exploration-ui-resume', '--exploration-resume',
                       dest='exploration_ui_resume', help=argparse.SUPPRESS)
    return root


def envelope(operation, observed, status='ok', reason_code=None):
    return dict(operation_id=str(uuid4()), operation=operation, installation_id=None, status=status,
                reason_code=reason_code, observed=observed, evidence_refs=[])


def version(args):
    observed = toolchain.identities()
    if args.json:
        print(json.dumps(envelope('version', observed), indent=2))
        return 0
    lock = observed['lock']
    print('edition   local')
    print('uv        ' + observed['tool']['uv'])
    print('tools     deployment/locks/tools.json sha256 ' + observed['tool']['tools_json_sha256'])
    print('python    ' + observed['python']['version'] + ' (build ' + str(observed['python']['build']) + ')')
    print('lock      uv.lock sha256 ' + lock['uv_lock_sha256'])
    print('project   pyproject.toml sha256 ' + lock['pyproject_sha256'])
    for group, state in lock['environments'].items():
        print(f'{group:<9} ' + state['path'] + ('' if state['installed'] else ' (not installed)'))
    print('release   none installed (checkout ' + str(observed['release']['checkout_commit']) + ')')
    return 0


def dev_check(args):
    if args.list == (args.group is not None):
        raise toolchain.ToolchainError('dev check takes a group name or --list', 2)
    if args.group_class is not None and not args.list:
        raise toolchain.ToolchainError('--class is valid only with --list', 2)
    if args.jobs is not None and args.group != 'qualification':
        raise toolchain.ToolchainError('--jobs is valid only with qualification', 2)
    runner = (['--list', *(['--class', args.group_class] if args.group_class else [])] if args.list
              else ['--group', args.group, *(['--units-mixed-repair'] if args.units_mixed_repair else []),
                    *(['--exploration-ui-resume', args.exploration_ui_resume]
                      if args.exploration_ui_resume else []),
                    *(['--jobs', str(args.jobs)] if args.jobs is not None else [])])
    toolchain.provision('contract')
    interpreter = str(toolchain.provision('native'))
    paths = toolchain.local_paths()
    # The runner takes its interpreters only from the locked environments.
    environment = {k: v for k, v in os.environ.items() if k not in (paths.NATIVE_PYTHON, paths.CONTRACT_PYTHON)}
    os.chdir(toolchain.REPO)
    sys.stdout.flush()
    sys.stderr.flush()
    os.execve(interpreter, [interpreter, '-I', '-B', str(toolchain.REPO / 'deployment/checks.py'), *runner],
              environment)


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == 'version':
            return version(args)
        if args.command == 'dev' and args.dev_command == 'check':
            return dev_check(args)
        raise toolchain.ToolchainError('unknown command', 2)
    except toolchain.ToolchainError as error:
        if args.json:
            print(json.dumps(envelope(args.command, {}, status='refused', reason_code='toolchain'), indent=2))
        print('hyprn-mvp: ' + str(error), file=sys.stderr)
        return error.code
