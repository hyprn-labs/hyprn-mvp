"""Explicit owner recovery of a verified, stopped, pre-upload AiiDA process.

The host must first stop the native writer and hold its execution lock. This is
not a retry or a public cancellation endpoint; it never steps a process.
"""

import hashlib
import json


def checkpoint_identity(node):
    return hashlib.sha256(json.dumps(node.checkpoint, sort_keys=True).encode()).hexdigest()


def terminate_paused(node, expected):
    from aiida import orm
    from aiida.manage import get_manager
    from aiida.engine.utils import loop_scope
    from plumpy import persistence

    if (not isinstance(node, orm.CalcJobNode)
            or node.uuid != expected['uuid']
            or node.process_type != expected['process_type']
            or node.process_state.value != 'waiting'
            or not node.paused or node.is_sealed
            or node.get_job_id() is not None or node.get_remote_workdir() is not None
            or node.base.links.get_outgoing().all_link_labels()
            or node.checkpoint is None
            or checkpoint_identity(node) != expected['checkpoint_sha256']):
        raise ValueError('Exact paused pre-upload checkpoint required')
    runner = get_manager().create_runner(communicator=None)
    process = None
    try:
        with loop_scope(runner.loop):
            checkpoint = runner.persister.load_checkpoint(node.pk)
            process = checkpoint.unbundle(persistence.LoadSaveContext(runner=runner))
            if process.node.uuid != node.uuid or type(process) is not node.process_class:
                raise ValueError('Checkpoint process identity changed')
            # No scheduler job exists. Use AiiDA's lifecycle to seal the original
            # node; do not resume the checkpoint or assign database state directly.
            terminated = process.kill(
                msg_text='Verified pre-upload owner recovery', force_kill=True)
            if terminated is not True:
                raise ValueError('Paused process termination refused')
            if (not process.node.is_sealed or process.node.process_state.value != 'killed'
                    or process.node.get_job_id() is not None
                    or process.node.base.links.get_outgoing().all_link_labels()):
                raise ValueError('Paused process termination is unconfirmed')
            return {'uuid': process.node.uuid, 'state': 'killed', 'sealed': True}
    finally:
        if process is not None:
            process.close()
        runner.close()
