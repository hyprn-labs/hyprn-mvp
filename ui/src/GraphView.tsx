import { GraphCanvas } from './design/graph';
import type { ReactNode } from 'react';
import type { Connection, Instance, ModelDraftRead4, ModelRevisionRead4, PortRead3, PortRef } from './contract';
import type { Selection } from './workspaceModel';

// Projection helpers shared by the canonical model view (ModelView.tsx) and the graph canvas.
export type Snapshot = ModelDraftRead4 | ModelRevisionRead4;
export type Node = { instance: Instance; ports: PortRead3[]; incomplete: boolean };
export type Exchange = { key: string; source: string; target: string; links: Connection[] };
export type Projection = { nodes: Node[]; groups: Exchange[]; invalid: Connection[] };
export type Trace = 'none' | 'incoming' | 'outgoing' | 'upstream' | 'downstream';
export function project(snapshot: Snapshot): Projection {
  const nodes = snapshot.instances.filter(i => i.instance_id !== snapshot.root_instance_id).map(instance => {
    const definition = snapshot.definitions.find(d => d.definition_version_id === instance.definition_version_id);
    return { instance, ports: definition?.ports ?? [], incomplete: !definition || !definition.ports.length || !definition.source_refs.length };
  });
  const groups = new Map<string, Exchange>(); const invalid: Connection[] = [];
  const port = (ref: PortRef) => nodes.find(n => n.instance.instance_id === ref.instance_id)?.ports.find(p => p.port_id === ref.port_id);
  for (const link of snapshot.connections) {
    if (port(link.source_ref)?.direction !== 'output' || port(link.target_ref)?.direction !== 'input') { invalid.push(link); continue; }
    const source = link.source_ref.instance_id, target = link.target_ref.instance_id, key = source + ':' + target;
    if (!groups.has(key)) groups.set(key, { key, source, target, links: [] });
    groups.get(key)!.links.push(link);
  }
  return { nodes, groups: [...groups.values()], invalid };
}
export function selectedInstances(selection: Selection, groups: Exchange[]): string[] {
  if (selection.kind === 'instance' || selection.kind === 'variable') return [selection.instance_id];
  if (selection.kind === 'connection_group') return [selection.source_instance_id, selection.target_instance_id];
  if (selection.kind === 'connection') { const group = groups.find(g => g.links.some(l => l.connection_id === selection.connection_id)); return group ? [group.source, group.target] : []; }
  return [];
}
export function traceRelationships(groups: Exchange[], seeds: string[], mode: Trace, selection?: Selection) {
  const nodes = new Set(seeds), links = new Set<string>();
  if (mode === 'none') return { nodes: new Set<string>(), links };
  const incoming = mode === 'incoming' || mode === 'upstream';
  const recursive = mode === 'upstream' || mode === 'downstream'; const queue = [...seeds];
  while (queue.length) {
    const id = queue.shift()!;
    for (const group of groups) {
      if ((incoming ? group.target : group.source) !== id) continue;
      const matching = group.links.filter(link => !selection || selection.kind !== 'variable' || !seeds.includes(id) ||
        (incoming ? link.target_ref.port_id : link.source_ref.port_id) === selection.port_id);
      if (!matching.length) continue;
      matching.forEach(link => links.add(link.connection_id)); const next = incoming ? group.source : group.target;
      if (!nodes.has(next)) { nodes.add(next); if (recursive) queue.push(next); }
    }
  }
  return { nodes, links };
}
export function groupSelected(group: Exchange, selection: Selection) {
  return selection.kind === 'connection_group' ? group.source === selection.source_instance_id && group.target === selection.target_instance_id :
    selection.kind === 'connection' && group.links.some(l => l.connection_id === selection.connection_id);
}
export function selectGroup(group: Exchange): Selection { return { kind: 'connection_group', source_instance_id: group.source, target_instance_id: group.target, connection_ids: group.links.map(l => l.connection_id) }; }
export type RevealTarget = { instance_id: string; port_id?: string; request: number };
export type ViewProps = {
  portContent?: (instanceId: string, port: PortRead3) => ReactNode;
  highlightedPorts?: Set<string>;
  reveal?: RevealTarget;
  projection: Projection;
  selection: Selection;
  onSelect: (selection: Selection) => void;
  trace: ReturnType<typeof traceRelationships>;
};
export const portSelected = (selection: Selection, id: string, port: string) => selection.kind === 'variable' && selection.instance_id === id && selection.port_id === port;
export const isFree = (projection: Projection, id: string, port: string) => !projection.groups.some(g => g.links.some(l => l.target_ref.instance_id === id && l.target_ref.port_id === port));
export const isResponse = (projection: Projection, id: string, port: string) => !projection.groups.some(g => g.links.some(l => l.source_ref.instance_id === id && l.source_ref.port_id === port));

export function GraphView(props: ViewProps) { return <GraphCanvas {...props} />; }

