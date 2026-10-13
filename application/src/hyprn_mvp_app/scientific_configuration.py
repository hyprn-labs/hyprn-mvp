"""Literal scientific snapshots for the private modeling boundary.

The saved application digest and private projection digest have distinct inputs.
This module never resolves sources, converts values, or imports a numerical engine.
"""
from copy import deepcopy

from .contracts import digest, validate


def project_scientific_configuration(configuration):
    """Copy exact scientific bytes, removing versioned application authority."""
    if not isinstance(configuration, dict) or configuration.get('schema_version') not in ('1', '2', '3', '4'):
        raise ValueError('Unsupported configuration version')
    immutable = 'configuration_revision_id' in configuration
    version = configuration['schema_version']
    validate(('ConfigurationRevision' if immutable else 'ConfigurationCandidate') + version, configuration)
    if immutable and configuration['digest'] != digest({k: v for k, v in configuration.items() if k != 'digest'}):
        raise ValueError('Full configuration digest mismatch')
    targets = [(i['target']['instance_id'], i['target']['port_id']) for i in configuration['inputs']]
    if len(set(targets)) != len(targets):
        raise ValueError('Duplicate configuration target')
    projected = deepcopy(configuration)
    private_version='3' if version=='4' else version
    if version=='4':
        projected['schema_version']='3'
        del projected['approach_binding']
    if version in ('2', '3', '4'):
        del projected['context_source']
        del projected['derivation']
        for item in projected['inputs']:
            del item['result_binding']
        removed={'result_linked_inputs/1'}
        if version in ('3','4'):
            del projected['assumptions']
            del projected['general_context_evidence_version_ids']
            removed.add('configuration_assumptions/1')
        projected['required_capabilities'] = [c for c in projected['required_capabilities'] if c not in removed]
        if immutable:
            projected['digest'] = digest({k: v for k, v in projected.items() if k != 'digest'})
        validate(('ModelingConfigurationRevision' if immutable else 'ModelingConfiguration')+private_version, projected)
    return projected


def scientific_configuration_digest(configuration):
    """Digest exact projection bytes excluding its immutable digest field."""
    projected = project_scientific_configuration(configuration)
    return digest({k: v for k, v in projected.items() if k != 'digest'})
