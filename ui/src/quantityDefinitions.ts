import type { ApproachElementRef1 } from './contract';
import type { Snapshot } from './GraphView';
import { unitLabel } from './unitLabels';

/** One exact occurrence, never a symbol lookup or a model-wide port-ID lookup. */
export function quantityDefinitions(model: Snapshot) {
  const revision = 'model_revision_id' in model ? model.model_revision_id : model.draft_revision;
  return model.instances.flatMap(instance => {
    const definition = model.definitions.find(d => d.definition_version_id === instance.definition_version_id);
    if (!definition) return [];
    return definition.ports.map(port => ({
      key: [model.model_id, revision, instance.instance_id, definition.definition_version_id, port.port_id].join('/'),
      model_id: model.model_id, revision, instance, definition, port,
      statement: 'quantity_definitions' in definition ? definition.quantity_definitions.find(q => q.port_id === port.port_id)?.statement ?? null : null,
      unit: unitLabel(port.units),
    }));
  });
}
export type QuantityDefinition = ReturnType<typeof quantityDefinitions>[number];

/** References narrow the same projection; connection references expose both exact endpoints. */
export function referencedQuantities(model: Snapshot, refs: ApproachElementRef1[]) {
  return quantityDefinitions(model).filter(q => refs.some(ref =>
    ref.kind === 'model' ||
    ref.kind === 'instance' && ref.instance_id === q.instance.instance_id ||
    ref.kind === 'port' && ref.instance_id === q.instance.instance_id && ref.port_id === q.port.port_id ||
    ref.kind === 'connection' && model.connections.some(c => c.connection_id === ref.connection_id &&
      [c.source_ref, c.target_ref].some(p => p.instance_id === q.instance.instance_id && p.port_id === q.port.port_id))
  ));
}

/** Component instances an exact reference set covers; the model root is structure, not a component. */
export function referencedInstances(model: Snapshot, refs: ApproachElementRef1[]) {
  return model.instances.filter(i => i.instance_id !== model.root_instance_id && refs.some(ref =>
    ref.kind === 'model' ||
    (ref.kind === 'instance' || ref.kind === 'port') && ref.instance_id === i.instance_id ||
    ref.kind === 'connection' && model.connections.some(c => c.connection_id === ref.connection_id &&
      [c.source_ref, c.target_ref].some(p => p.instance_id === i.instance_id))
  ));
}
