import { unitLabel } from '../unitLabels';
import { useEffect, useId, useRef, useState } from 'react';
import { Button, ModelNode } from './components';
import { ActionDialog } from './primitives';
import {
  groupSelected,
  selectGroup,
  selectedInstances,
  portSelected,
  isFree,
  type ViewProps,
} from '../GraphView';

// Geometry is presentation only; snapshot and selected identity remain with the caller.
export function GraphCanvas({
  projection,
  selection,
  onSelect,
  trace,
  reveal,
  highlightedPorts,
  portContent,
}: ViewProps) {
  const marker = useId().replaceAll(':', '');
  const viewport = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [availableWidth, setAvailableWidth] = useState(720);
  useEffect(() => {
    const element = viewport.current;
    if (!element) return;
    const observer = new ResizeObserver(() => setAvailableWidth(element.clientWidth));
    observer.observe(element);
    return () => observer.disconnect();
  }, [projection.nodes.length]);
  const gesture = useRef<{ x: number; y: number; origin: typeof pan } | null>(null);
  const maxPorts = Math.max(1, ...projection.nodes.map((n) => n.ports.length));
  const columns = portContent ? 1 : projection.nodes.length > 4 ? 3 : 2;
  const token = (name: string) =>
    parseFloat(getComputedStyle(document.documentElement).getPropertyValue(name));
  const pitch = token('--space-12');
  const portHeight = portContent ? pitch * 5 : token('--control-floor');
  const nodeWidth = portContent
    ? Math.max(pitch * 5, (availableWidth - pitch * 2 - (columns - 1) * pitch) / columns)
    : pitch * 4 + token('--space-6');
  const portCenter = token('--control-floor') * 1.5 + (portContent ? token('--space-2') : 0);
  const columnWidth = nodeWidth + (portContent ? pitch : pitch * 1.5),
    top = portContent ? pitch / 2 : pitch,
    left = token('--space-6');
  const row = portContent ? pitch * 10 : portHeight * (maxPorts + 1) + pitch * 2;
  const width = columns * columnWidth + left * 2;
  const height = Math.max(pitch * 7, Math.ceil(projection.nodes.length / columns) * row + top);
  const positions = new Map(
    projection.nodes.map((n, i) => [
      n.instance.instance_id,
      { x: left + (i % columns) * columnWidth, y: top + Math.floor(i / columns) * row },
    ]),
  );
  function fit() {
    setZoom(1);
    setPan({ x: 0, y: 0 });
    viewport.current?.scrollTo(0, 0);
  }
  function focus() {
    const ids = selectedInstances(selection, projection.groups),
      point = positions.get(ids[0]);
    if (!point) return;
    setZoom(1.5);
    setPan({
      x: (viewport.current?.clientWidth ?? width) / 2 - (point.x + nodeWidth / 2) * 1.5,
      y: pitch * 2 - point.y * 1.5,
    });
    viewport.current?.focus();
  }
  useEffect(() => {
    if (!reveal) return;
    const point = positions.get(reveal.instance_id);
    if (!point) return;
    setZoom(1);
    setPan({ x: 0, y: 0 });
    const frame = requestAnimationFrame(() => {
      const head = viewport.current?.querySelector<HTMLElement>(
        `[data-instance="${CSS.escape(reveal.instance_id)}"]`,
      );
      const element = reveal.port_id
        ? (head
            ?.closest('.hf-node')
            ?.querySelector<HTMLElement>(`[data-port="${CSS.escape(reveal.port_id)}"]`) ?? head)
        : head;
      const portIndex = reveal.port_id
        ? (projection.nodes
            .find((n) => n.instance.instance_id === reveal.instance_id)
            ?.ports.findIndex((p) => p.port_id === reveal.port_id) ?? -1)
        : -1;
      viewport.current?.scrollTo({
        left: Math.max(0, point.x - pitch),
        top: Math.max(0, point.y + (portIndex + 1) * portHeight - pitch),
      });
      element?.focus({ preventScroll: true });
    });
    return () => cancelAnimationFrame(frame);
  }, [reveal]);
  return (
    <>
      <div className="hf-view-toolbar" role="group" aria-label="Graph view controls">
        <Button
          size="sm"
          disabled={zoom <= 1}
          onClick={() => setZoom((z) => Math.max(1, z - 0.25))}
        >
          Zoom out
        </Button>
        <span className="hf-mono" aria-label="Graph zoom" aria-live="polite">
          {Math.round(zoom * 100)}%
        </span>
        <Button
          size="sm"
          disabled={zoom >= 2.5}
          onClick={() => setZoom((z) => Math.min(2.5, z + 0.25))}
        >
          Zoom in
        </Button>
        {!portContent && (
          <>
            <Button size="sm" onClick={fit}>
              Reset view
            </Button>
            <Button size="sm" disabled={selection.kind === 'none'} onClick={focus}>
              Focus selection
            </Button>
            <ActionDialog title="How to read the graph" label="Help?" size="sm">
              <p>
                Arrows connect component outputs to inputs. Inputs without incoming connections need
                values in a configuration.
              </p>
              <p>
                Drag the background to pan. With the diagram focused, use the arrow keys to pan.
                Reset view returns to 100%. Layout does not set numerical order.
              </p>
            </ActionDialog>
          </>
        )}
      </div>
      {!projection.nodes.length ? (
        <p>No components in this model.</p>
      ) : (
        <div
          className={'graph-viewport' + (portContent ? ' hf-graph-exploration' : '')}
          role="region"
          aria-label="Directed component diagram"
          ref={viewport}
          tabIndex={0}
          onKeyDown={(e) => {
            if (
              e.target !== e.currentTarget ||
              !['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(e.key)
            )
              return;
            e.preventDefault();
            setPan((p) => ({
              x: p.x + (e.key === 'ArrowLeft' ? pitch : e.key === 'ArrowRight' ? -pitch : 0),
              y: p.y + (e.key === 'ArrowUp' ? pitch : e.key === 'ArrowDown' ? -pitch : 0),
            }));
          }}
          onPointerDown={(e) => {
            if (e.target === e.currentTarget || (e.target as Element).tagName === 'svg') {
              gesture.current = { x: e.clientX, y: e.clientY, origin: pan };
              e.currentTarget.setPointerCapture(e.pointerId);
            }
          }}
          onPointerMove={(e) => {
            if (gesture.current)
              setPan({
                x: gesture.current.origin.x + (e.clientX - gesture.current.x),
                y: gesture.current.origin.y + (e.clientY - gesture.current.y),
              });
          }}
          onPointerUp={() => {
            gesture.current = null;
          }}
          onPointerCancel={() => {
            gesture.current = null;
          }}
        >
          <svg
            viewBox={`0 0 ${width * zoom} ${height * zoom}`}
            width={width * zoom}
            height={height * zoom}
            aria-label="Directed graph"
            className="connected-graph"
          >
            <defs>
              <marker
                id={marker}
                viewBox="0 0 10 10"
                refX="9"
                refY="5"
                markerWidth="8"
                markerHeight="8"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill="context-stroke" />
              </marker>
            </defs>
            <g transform={`translate(${pan.x} ${pan.y}) scale(${zoom})`}>
              {projection.groups.map((g, i) => {
                const from = positions.get(g.source)!,
                  to = positions.get(g.target)!;
                const x = from.x + nodeWidth,
                  end = to.x;
                const source = projection.nodes.find((n) => n.instance.instance_id === g.source)!;
                const target = projection.nodes.find((n) => n.instance.instance_id === g.target)!;
                const sourceIndex = source.ports.findIndex(
                  (p) => p.port_id === g.links[0].source_ref.port_id,
                );
                const targetIndex = target.ports.findIndex(
                  (p) => p.port_id === g.links[0].target_ref.port_id,
                );
                const y =
                  from.y + portCenter + (portContent ? 0 : Math.max(0, sourceIndex) * portHeight);
                const endY =
                  to.y + portCenter + (portContent ? 0 : Math.max(0, targetIndex) * portHeight);
                const feedback = to.y < from.y || (to.y === from.y && to.x <= from.x);
                const lane = pitch / 2 + ((i % 3) * pitch) / 3;
                const vertical = to.y > from.y && to.x === from.x;
                const adjacent = portContent && vertical && to.y - from.y === row;
                const labelX = adjacent
                  ? from.x + nodeWidth / 2 + pitch / 2
                  : vertical
                    ? portContent
                      ? width - pitch / 2
                      : x + pitch * 1.5
                    : (x + end) / 2;
                const labelY = adjacent
                  ? (from.y + pitch * 8 + to.y) / 2
                  : (y + endY) / 2 - pitch / 4;
                const d = adjacent
                  ? `M${from.x + nodeWidth / 2},${from.y + pitch * 8} V${to.y}`
                  : portContent
                    ? to.y === from.y && to.x > from.x
                      ? to.x - from.x <= columnWidth + 1
                        ? `M${x},${y} H${end}`
                        : `M${x},${y} H${x + pitch / 3} V${from.y - pitch / 3} ` +
                          `H${end - pitch / 3} V${endY} H${end}`
                      : `M${x},${y} H${width - pitch / 3 - ((i % 3) * pitch) / 8} ` +
                        `V${endY} H${to.x + nodeWidth}`
                    : vertical
                      ? `M${x},${y} C${x + pitch * 2},${y} ` +
                        `${end + columnWidth},${endY} ${end + nodeWidth},${endY}`
                      : feedback
                        ? `M${x},${y} C${x + lane},${y - pitch * 2} ` +
                          `${end - lane},${endY - pitch * 2} ${end},${endY}`
                        : `M${x},${y} C${x + pitch * 1.5},${y} ` +
                          `${end - pitch * 1.5},${endY} ${end},${endY}`;
                const symbols = g.links
                  .map(
                    (l) =>
                      projection.nodes
                        .find((n) => n.instance.instance_id === g.source)
                        ?.ports.find((p) => p.port_id === l.source_ref.port_id)?.code_symbol ??
                      'Missing port',
                  )
                  .join(', ');
                const active = groupSelected(g, selection),
                  traced = g.links.some((l) => trace.links.has(l.connection_id));
                return (
                  <g
                    key={g.key}
                    className={`graph-exchange ${active ? 'selected' : traced ? 'traced' : ''}`}
                    role="button"
                    tabIndex={0}
                    aria-label={
                      `Exchange ${g.links.length} links from ${source.instance.name} ` +
                      `to ${target.instance.name}`
                    }
                    aria-pressed={active}
                    data-group={g.key}
                    onClick={() => onSelect(selectGroup(g))}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        onSelect(selectGroup(g));
                      }
                    }}
                  >
                    <title>
                      {g.links.length} directed links · {g.source} → {g.target}
                      {feedback ? ' · feedback' : ''}
                    </title>
                    <path d={d} className="exchange-hit" />
                    <path d={d} markerEnd={`url(#${marker})`} />
                    <text x={labelX} y={labelY}>
                      {portContent
                        ? g.links.length + (g.links.length === 1 ? ' link' : ' links')
                        : g.links.length === 1
                          ? symbols + ' →'
                          : g.links.length + ' links'}
                      {feedback ? ' ↶' : ''}
                      {active && (
                        <tspan x={labelX} dy="1.25em" fontSize={token('--type-small-size')}>
                          {symbols.length > 40 ? symbols.slice(0, 40) + '…' : symbols}
                        </tspan>
                      )}
                    </text>
                  </g>
                );
              })}
              {projection.nodes.map(({ instance, ports, incomplete }, index) => {
                const p = positions.get(instance.instance_id)!;
                const active = selectedInstances(selection, projection.groups).includes(
                  instance.instance_id,
                );
                return (
                  <g
                    key={instance.instance_id}
                    className={
                      'diagram-node ' +
                      (active ? 'selected' : trace.nodes.has(instance.instance_id) ? 'traced' : '')
                    }
                  >
                    <foreignObject
                      x={p.x}
                      y={p.y}
                      width={nodeWidth}
                      height={portContent ? pitch * 8.5 : portHeight * (ports.length + 1) + pitch}
                    >
                      <ModelNode
                        className={portContent ? 'hf-node--explorer' : undefined}
                        name={instance.name}
                        index={index + 1}
                        instanceId={instance.instance_id}
                        title={
                          instance.name +
                          '\nInstance ' +
                          instance.instance_id +
                          '\nVersion ' +
                          instance.definition_version_id
                        }
                        selected={active}
                        nameSelected={
                          selection.kind === 'instance' &&
                          selection.instance_id === instance.instance_id
                        }
                        status={incomplete ? 'incomplete' : undefined}
                        onSelect={() =>
                          onSelect({ kind: 'instance', instance_id: instance.instance_id })
                        }
                        ports={ports.map((port) => ({
                          id: port.port_id,
                          name: portContent ? port.name : port.code_symbol,
                          dir: port.direction === 'input' ? 'in' : 'out',
                          content: portContent?.(instance.instance_id, port),
                          title:
                            port.name +
                            ' · ' +
                            port.code_symbol +
                            ' · ' +
                            unitLabel(port.units) +
                            '\n' +
                            instance.instance_id +
                            ' / ' +
                            port.port_id,
                          state:
                            port.direction === 'input'
                              ? isFree(projection, instance.instance_id, port.port_id)
                                ? 'free'
                                : 'connected'
                              : 'output',
                          selected:
                            portSelected(selection, instance.instance_id, port.port_id) ||
                            highlightedPorts?.has(instance.instance_id + '/' + port.port_id),
                          onSelect: () =>
                            onSelect({
                              kind: 'variable',
                              instance_id: instance.instance_id,
                              port_id: port.port_id,
                            }),
                        }))}
                      />
                    </foreignObject>
                  </g>
                );
              })}
            </g>
          </svg>
        </div>
      )}
    </>
  );
}
