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
import subprocess
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
    check.add_argument('--keep-scope', action='store_true', help='retain test scopes for 24 hours within the storage budget')
    check.add_argument('--units-mixed-repair', action='store_true', help=argparse.SUPPRESS)
    check.add_argument('--served-grep',
                       help='with ui-served: matching test titles only; not full group acceptance')
    check.add_argument('--exploration-ui-resume', '--exploration-resume',
                       dest='exploration_ui_resume', help=argparse.SUPPRESS)
    storage = dev_commands.add_parser('storage', help='retain and budget explicitly enrolled disposable experiments')
    actions = storage.add_subparsers(dest='action', required=True)
    for name in ('enroll', 'status', 'collect', 'run', 'staging-enroll', 'staging-status', 'staging-collect'):
        action = actions.add_parser(name)
        action.add_argument('--config', help='absolute storage policy file')
        action.add_argument('--root', action='append', default=[], help='existing disposable experiment folder to enroll')
        action.add_argument('--budget-bytes', type=int)
        action.add_argument('--reserve-bytes', type=int)
        action.add_argument('program', nargs=argparse.REMAINDER, help='run: command after --; collect before and after')
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
    if args.served_grep is not None and args.group != 'ui-served':
        raise toolchain.ToolchainError('--served-grep is valid only with ui-served', 2)
    runner = (['--list', *(['--class', args.group_class] if args.group_class else [])] if args.list
              else ['--group', args.group, *(['--units-mixed-repair'] if args.units_mixed_repair else []),
                    *(['--exploration-ui-resume', args.exploration_ui_resume]
                      if args.exploration_ui_resume else []),
                    *(['--jobs', str(args.jobs)] if args.jobs is not None else [])])
    if args.keep_scope:
        if args.list or args.group == 'qualification':
            raise toolchain.ToolchainError('--keep-scope requires one check group', 2)
        runner.append('--keep-scope')
    if args.served_grep is not None:
        runner.extend(['--served-grep', args.served_grep])
    if not args.list:
        experiment_module().automatic()
        import staging_storage
        staging_storage.automatic()
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


def experiment_module():
    toolchain.local_paths()
    import experiment_storage
    if experiment_storage.__file__ != str(toolchain.REPO / 'deployment/experiment_storage.py'):
        raise toolchain.ToolchainError('experiment storage imported outside checkout')
    return experiment_storage


def dev_storage(args):
    storage = experiment_module()
    if args.action.startswith('staging-'):
        import staging_storage
        path = staging_storage.policy_path(args.config)
        if path is None:
            raise ValueError('Set --config or HYPRN_MVP_DATA_ROOT')
        if args.program:
            raise ValueError('Staging storage commands do not take a program')
        if args.action == 'staging-enroll':
            if not args.root:
                raise ValueError('staging-enroll requires a parent --root')
            result = staging_storage.enroll(path, args.root, args.budget_bytes, args.reserve_bytes)
        else:
            if args.root or args.budget_bytes is not None or args.reserve_bytes is not None:
                raise ValueError('Root and budget options require staging-enroll')
            result = staging_storage.collect(path, apply=args.action == 'staging-collect')
        print(json.dumps(result, indent=2), flush=True)
        return 0 if result.get('admitted', True) else 2
    path = storage.configuration(args.config)
    if path is None:
        raise toolchain.ToolchainError('Set --config or HYPRN_MVP_DATA_ROOT for the experiment policy', 2)
    if args.action == 'enroll':
        if not args.root or args.program:
            raise ValueError('enroll requires --root and no command')
        print(json.dumps(storage.enroll(path, args.root, args.budget_bytes, args.reserve_bytes), indent=2))
        return 0
    if args.budget_bytes is not None or args.reserve_bytes is not None or (args.root and args.action != 'run'):
        raise ValueError('Budget options require enroll; roots require enroll or run')
    if args.action == 'run' and args.root:
        storage.enroll(path, args.root)
    program = args.program[1:] if args.program[:1] == ['--'] else args.program
    if (args.action == 'run') != bool(program):
        raise ValueError('Only run requires a command after --')
    report = storage.collect(path, apply=args.action != 'status')
    print(json.dumps(report, indent=2), flush=True)
    if not report['admitted']:
        return 2
    if args.action == 'run':
        try:
            status = subprocess.call(program)
        finally:
            after = storage.collect(path, apply=True)
            print(json.dumps(after, indent=2), flush=True)
        return status or (0 if after['admitted'] else 2)
    return 0


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == 'version':
            return version(args)
        if args.command == 'dev' and args.dev_command == 'storage':
            return dev_storage(args)
        if args.command == 'dev' and args.dev_command == 'check':
            return dev_check(args)
        raise toolchain.ToolchainError('unknown command', 2)
    except (toolchain.ToolchainError, ValueError, OSError, subprocess.SubprocessError) as error:
        if args.json:
            print(json.dumps(envelope(args.command, {}, status='refused', reason_code='toolchain'), indent=2))
        print('hyprn-mvp: ' + str(error), file=sys.stderr)
        return getattr(error, 'code', 2)
