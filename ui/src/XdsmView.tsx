import { DataTable } from './design';
import { useEffect, useRef } from 'react';
import { Button, ActionDialog } from './design';
import { groupSelected, selectGroup, portSelected, isFree, isResponse, type ViewProps } from './GraphView';

export function XdsmView({ projection, selection, onSelect, trace, reveal }: ViewProps) {
  const table = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!reveal) return;
    const frame = requestAnimationFrame(() => {
      const target = table.current?.querySelector<HTMLButtonElement>(`[data-instance="${CSS.escape(reveal.instance_id)}"]`);
      target?.scrollIntoView({ block: 'nearest', inline: 'center' }); target?.focus({ preventScroll: true });
    });
    return () => cancelAnimationFrame(frame);
  }, [reveal]);
  if (!projection.nodes.length) return <p>No components in this model.</p>;
  return <><div className="hf-view-toolbar"><ActionDialog title="How to read XDSM" label="Help?" size="sm"><p>Components sit on the diagonal. Read outputs across the producer’s row and inputs down the consumer’s column. Free inputs appear above; unconnected outputs appear at the right boundary. This is a static scalar data-flow view; it does not show numerical iteration or execution order.</p></ActionDialog></div><div ref={table} className="xdsm-scroll" role="region" aria-label="Component exchange matrix" tabIndex={0}><DataTable className="xdsm"><caption>Component exchanges · presentation order only</caption>
    <thead><tr><th scope="col">Producer / consumer</th>{projection.nodes.map((n, i) => <th scope="col" key={n.instance.instance_id} data-column-id={n.instance.instance_id}>{i + 1}. {n.instance.name}</th>)}<th scope="col">Responses</th></tr></thead>
    <tbody><tr className="xdsm-boundary"><th scope="row">Free inputs</th>{projection.nodes.map(n => <td key={n.instance.instance_id}>{n.ports.filter(p => p.direction === 'input' && isFree(projection, n.instance.instance_id, p.port_id)).map(p => <Button key={p.port_id} aria-pressed={portSelected(selection, n.instance.instance_id, p.port_id)} title={`${n.instance.instance_id}/${p.port_id}`} onClick={() => onSelect({ kind: 'variable', instance_id: n.instance.instance_id, port_id: p.port_id })}>{p.code_symbol} · free input</Button>)}</td>)}<td aria-label="No boundary exchange">—</td></tr>
      {projection.nodes.map((producer, i) => <tr key={producer.instance.instance_id}><th scope="row">{i + 1}. {producer.instance.name}</th>{projection.nodes.map(consumer => {
        const source = producer.instance.instance_id, target = consumer.instance.instance_id;
        const group = projection.groups.find(g => g.source === source && g.target === target);
        return <td key={target} className={source === target ? 'xdsm-diagonal' : group ? 'xdsm-exchange' : 'xdsm-empty'}>
          {source === target && <Button data-instance={source} aria-pressed={selection.kind === 'instance' && selection.instance_id === source} className={trace.nodes.has(source) ? 'traced' : ''} title={`Instance ${source}\nVersion ${producer.instance.definition_version_id}`} onClick={() => onSelect({ kind: 'instance', instance_id: source })}>{producer.instance.name}{producer.incomplete && ' · ⚠ incomplete'}</Button>}
          {group && <Button data-group={group.key} aria-pressed={groupSelected(group, selection)} className={group.links.some(l => trace.links.has(l.connection_id)) ? 'traced' : ''} onClick={() => onSelect(selectGroup(group))}>{group.links.length} {group.links.length === 1 ? 'connection' : 'connections'}<span>{group.links.map(l => `${producer.ports.find(p => p.port_id === l.source_ref.port_id)?.code_symbol} → ${consumer.ports.find(p => p.port_id === l.target_ref.port_id)?.code_symbol}`).join(', ')}</span></Button>}
          {source !== target && !group && <span aria-label="No connection">·</span>}
        </td>;
      })}<td className="xdsm-boundary">{producer.ports.filter(p => p.direction === 'output' && isResponse(projection, producer.instance.instance_id, p.port_id)).map(p => <Button key={p.port_id} aria-pressed={portSelected(selection, producer.instance.instance_id, p.port_id)} title={`${producer.instance.instance_id}/${p.port_id}`} onClick={() => onSelect({ kind: 'variable', instance_id: producer.instance.instance_id, port_id: p.port_id })}>{p.code_symbol} · response</Button>)}</td></tr>)}
    </tbody></DataTable></div></>;
}
