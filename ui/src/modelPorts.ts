import type { ModelDraftRead4, ModelRevisionRead4 } from './contract';

export function modelPorts(model: ModelDraftRead4 | ModelRevisionRead4) {
  return model.instances.flatMap((instance) =>
    (
      model.definitions.find((d) => d.definition_version_id === instance.definition_version_id)
        ?.ports ?? []
    ).map((port) => ({
      ...port,
      target: { instance_id: instance.instance_id, port_id: port.port_id },
      label: `${instance.name} · ${port.name}`,
    })),
  );
}
