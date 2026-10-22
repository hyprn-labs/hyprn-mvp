"""Pure quantity projection from an integrity-checked frozen configuration."""

from .execution_bundle import validate_frozen_configuration
from .units import port_units


def _key(target):
    return target['instance_id'], target['port_id']


def quantities(frozen):
    """Project active occurrences only; reject ambiguous or incomplete assignments."""
    validate_frozen_configuration(frozen)
    model, configuration = frozen['model_snapshot'], frozen['configuration']
    units = port_units(model)
    versions = {d['definition_version_id']: d for d in model['definitions']}
    ports = {}
    for instance in model['instances']:
        version = instance['definition_version_id']
        for port in versions[version]['ports']:
            target = dict(instance_id=instance['instance_id'], port_id=port['port_id'])
            key = _key(target)
            if key in ports:
                raise ValueError('Duplicate port occurrence')
            ports[key] = (
                port['direction'],
                dict(
                    target=target,
                    definition_version_id=version,
                    name=port['name'],
                    instance_name=instance['name'],
                    units=units[(key[0], version, key[1])],
                ),
            )
    connected = {}
    for connection in model['connections']:
        target, source = _key(connection['target_ref']), _key(connection['source_ref'])
        if (
            target in connected
            or target not in ports
            or source not in ports
            or ports[target][0] != 'input'
            or ports[source][0] != 'output'
        ):
            raise ValueError('Invalid connection occurrence')
        connected[target] = connection['source_ref']
    assignments = {}
    for item in configuration['inputs']:
        key = _key(item['target'])
        if key in assignments:
            raise ValueError('Duplicate input assignment')
        assignments[key] = item
    free = {key for key, (direction, _) in ports.items() if direction == 'input'} - set(
        connected
    )
    if free != set(assignments):
        raise ValueError('Exactly one explicit assignment per free input is required')
    inputs, outputs = [], []
    for key, (direction, port) in ports.items():
        if direction == 'input':
            binding = (
                dict(kind='connected', source=connected[key])
                if key in connected
                else dict(kind='free', assignment=assignments[key])
            )
            inputs.append(dict(**port, binding=binding))
        elif direction == 'output':
            outputs.append(port)
    return inputs, outputs
