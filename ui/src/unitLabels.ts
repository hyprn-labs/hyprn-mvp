import type { ModelDraftRead4, ModelRevisionRead4, UnitCatalog1, UnitDeclaration1 } from './contract';

/** Local physical text stays verbatim until the public catalog admits it. */
export type UnitDraft = { kind: 'unspecified' } | { kind: 'dimensionless' } | { kind: 'physical'; expression: string };
export type UnitValue = string | UnitDraft;
export function unitLabel(value: UnitValue): string {
  if (typeof value === 'string') return value === '' ? 'Dimensionless' : value;
  return value.kind === 'unspecified' ? 'Not specified' : value.kind === 'dimensionless' ? 'Dimensionless' : value.expression;
}
/** Undefined means unresolved; the historical empty string means dimensionless. */
export function resolvedUnit(value: UnitValue): string | undefined {
  if (typeof value === 'string') return value;
  return value.kind === 'unspecified' ? undefined : value.kind === 'dimensionless' ? '' : value.expression;
}
export function unitDraft(value: UnitValue): UnitDraft {
  return typeof value === 'string' ? (value === '' ? {kind:'dimensionless'} : {kind:'physical',expression:value}) : value;
}
export function unitDeclaration(value: UnitDraft, catalog: UnitCatalog1 | null): UnitDeclaration1 {
  if (!catalog) throw new Error('Unit guidance is unavailable. Retry unit guidance. Your edits are kept.');
  if (value.kind !== 'physical') return value;
  const expression = catalog.supported_units.find(unit => unit === value.expression);
  if (!expression) throw new Error('This unit spelling is not supported. Choose a supported spelling. Your edits are kept.');
  return {kind:'physical',expression};
}
/** Inspect actual instance bindings, never every retained definition version. */
export function unresolvedModelUnits(model: ModelDraftRead4 | ModelRevisionRead4) {
  return model.instances.flatMap(instance => {
    const definition = model.definitions.find(d => d.definition_version_id === instance.definition_version_id);
    return (definition?.ports ?? []).filter(port => resolvedUnit(port.units) === undefined).map(port => ({
      instance_id: instance.instance_id, definition_version_id: instance.definition_version_id,
      port_id: port.port_id, component: instance.name, quantity: port.name,
    }));
  });
}
