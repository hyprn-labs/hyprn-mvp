import { modelRoutes } from './graphRouting';
import { unitLabel } from '../unitLabels';
import { useEffect, useLayoutEffect, useId, useRef, useState } from 'react';
import { Button, ModelNode } from './components';
import { SectionHelp } from './primitives';
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
  toolbarEnd,
}: ViewProps) {
  const marker = useId().replaceAll(':', '');
  const viewport = useRef<HTMLDivElement>(null);
  const content = useRef<SVGGElement>(null);
  const autoFit = useRef(true);
  const revealing = useRef(false);
  const [hovered, setHovered] = useState('');
  const [focused, setFocused] = useState('');
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [availableWidth, setAvailableWidth] = useState(720);
  const [availableHeight, setAvailableHeight] = useState(480);
  useEffect(() => {
    const element = viewport.current;
    if (!element) return;
    const observer = new ResizeObserver(() => {
      if (element.clientWidth && element.clientHeight) {
        setAvailableWidth(element.clientWidth);
        setAvailableHeight(element.clientHeight);
      }
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [projection.nodes.length]);
  const [nodeHeights, setNodeHeights] = useState<Record<string, number>>({});
  const [portCenters, setPortCenters] = useState<Record<string, number>>({});
  useLayoutEffect(() => {
    if (!viewport.current) return;
    const observer = new ResizeObserver((entries) => {
      const centers: Record<string, number> = {};
      const heights: Record<string, number> = {};
      for (const entry of entries) {
        const element = entry.target as HTMLElement;
        const id = element.querySelector<HTMLElement>('[data-instance]')?.dataset.instance;
        if (!id) continue;
        heights[id] = Math.ceil(element.offsetHeight);
        const bounds = element.getBoundingClientRect();
        const scale = bounds.width / element.offsetWidth;
        if (scale > 0)
          element.querySelectorAll<HTMLElement>('[data-port]').forEach((port) => {
            const box = port.getBoundingClientRect();
            centers[id + '/' + port.dataset.port] = (box.y + box.height / 2 - bounds.y) / scale;
          });
      }
      setNodeHeights((previous) => {
        return Object.keys(heights).some((key) => previous[key] !== heights[key])
          ? { ...previous, ...heights }
          : previous;
      });
      setPortCenters((previous) => {
        const next = { ...previous, ...centers };
        return Object.keys(centers).some((key) => Math.abs((previous[key] ?? -1) - next[key]) > 0.5)
          ? next
          : previous;
      });
    });
    viewport.current.querySelectorAll('.hf-node').forEach((node) => observer.observe(node));
    return () => observer.disconnect();
  }, [portContent, projection.nodes]);
  const gesture = useRef<{ x: number; y: number; origin: typeof pan } | null>(null);
  const token = (name: string) =>
    parseFloat(getComputedStyle(document.documentElement).getPropertyValue(name));
  const pitch = token('--space-12');
  const columns = portContent
    ? 1
    : Math.max(
        1,
        Math.min(
          projection.nodes.length,
          3,
          availableWidth >= pitch * 15
            ? 3
            : Math.floor((availableWidth - pitch) / (pitch * 5 + pitch)),
        ),
      );
  const portHeight = portContent ? pitch * 5 : token('--row-dense');
  const nodeWidth = portContent
    ? Math.max(pitch * 13, (availableWidth - pitch * 2 - (columns - 1) * pitch) / columns)
    : Math.max(
        pitch * 5,
        Math.min(pitch * 6, (availableWidth - pitch * 2 - (columns - 1) * pitch) / columns),
      );
  const portCenter = token('--control-floor') * 1.5 + (portContent ? token('--space-2') : 0);
  const gap = portContent ? pitch : pitch * 2;
  const columnWidth = nodeWidth + gap,
    top = portContent ? pitch / 2 : pitch,
    left = token('--space-6');
  const width = columns * columnWidth + left * 2;
  const positions = new Map<string, { x: number; y: number }>();
  let nextTop = top;
  let rowHeight = 0;
  projection.nodes.forEach((n, i) => {
    if (!portContent && i > 0 && i % columns === 0) {
      nextTop += rowHeight + pitch;
      rowHeight = 0;
    }
    positions.set(n.instance.instance_id, {
      x: left + (i % columns) * columnWidth,
      y: nextTop,
    });
    if (portContent) nextTop += (nodeHeights[n.instance.instance_id] ?? pitch * 8) + pitch * 1.5;
    else
      rowHeight = Math.max(
        rowHeight,
        nodeHeights[n.instance.instance_id] ?? portHeight * n.ports.length + pitch * 2,
      );
  });
  const routes = portContent
    ? []
    : modelRoutes(projection, positions, portCenters, nodeWidth, gap, portHeight, portCenter);
  const endpointActive = (instance: string, port: string) =>
    routes.some(
      ({ link }) =>
        (link.connection_id === hovered ||
          link.connection_id === focused ||
          (selection.kind === 'connection' && selection.connection_id === link.connection_id)) &&
        [link.source_ref, link.target_ref].some(
          (ref) => ref.instance_id === instance && ref.port_id === port,
        ),
    );
  // Resolve close route hits by geometric distance, not SVG paint order. The wide
  // invisible targets remain usable at fit zoom without stealing a neighbouring lane.
  function nearestRoute(clientX: number, clientY: number) {
    let nearest = '',
      distance = Infinity;
    viewport.current
      ?.querySelectorAll<SVGPathElement>('.hf-model-route path:not(.exchange-hit)')
      .forEach((path) => {
        const matrix = path.getScreenCTM();
        if (!matrix) return;
        const length = path.getTotalLength();
        const steps = Math.max(1, Math.ceil((length * zoom) / 2));
        for (let i = 0; i <= steps; i++) {
          const point = path.getPointAtLength((length * i) / steps).matrixTransform(matrix);
          const d = Math.hypot(point.x - clientX, point.y - clientY);
          if (d < distance) {
            distance = d;
            nearest = path.parentElement?.dataset.connection ?? '';
          }
        }
      });
    return nearest;
  }
  const height = Math.max(pitch * 7, portContent ? nextTop : nextTop + rowHeight + pitch);
  function fit() {
    revealing.current = false;
    const box = content.current?.getBBox();
    if (!box || !box.width || !box.height || !availableWidth || !availableHeight) return;
    const scale = Math.min(
      1,
      (availableWidth - pitch) / box.width,
      (availableHeight - pitch) / box.height,
    );
    if (!(scale > 0 && Number.isFinite(scale))) return;
    autoFit.current = true;
    setZoom(scale);
    setPan({
      x: (availableWidth - box.width * scale) / 2 - box.x * scale,
      y: (availableHeight - box.height * scale) / 2 - box.y * scale,
    });
    viewport.current?.scrollTo(0, 0);
  }
  const identity = projection.nodes.map((n) => n.instance.instance_id).join('/');
  useLayoutEffect(() => {
    autoFit.current = true;
  }, [identity]);
  useLayoutEffect(() => {
    if (!portContent && autoFit.current) fit();
  }, [
    portContent,
    availableWidth,
    availableHeight,
    nodeHeights,
    portCenters,
    projection,
    selection,
  ]);
  function changeZoom(next: number) {
    revealing.current = false;
    autoFit.current = false;
    if (!portContent)
      setPan((p) => ({
        x: availableWidth / 2 - ((availableWidth / 2 - p.x) * next) / zoom,
        y: availableHeight / 2 - ((availableHeight / 2 - p.y) * next) / zoom,
      }));
    setZoom(next);
  }
  function focus() {
    revealing.current = false;
    const boxes = selectedInstances(selection, projection.groups).flatMap((id) => {
      const point = positions.get(id);
      return point ? [{ ...point, width: nodeWidth, height: nodeHeights[id] ?? pitch * 8 }] : [];
    });
    if (!boxes.length) return;
    const x = Math.min(...boxes.map((box) => box.x));
    const y = Math.min(...boxes.map((box) => box.y));
    const w = Math.max(...boxes.map((box) => box.x + box.width)) - x;
    const h = Math.max(...boxes.map((box) => box.y + box.height)) - y;
    autoFit.current = false;
    const scale = Math.min(1.5, (availableWidth - pitch) / w, (availableHeight - pitch) / h);
    setZoom(scale);
    setPan({
      x: (availableWidth - w * scale) / 2 - x * scale,
      y: (availableHeight - h * scale) / 2 - y * scale,
    });
    viewport.current?.focus();
  }
  useLayoutEffect(() => {
    revealing.current = !!reveal;
  }, [reveal]);
  useEffect(() => {
    if (!reveal || !revealing.current) return;
    if (
      !('instance_id' in selection) ||
      selection.instance_id !== reveal.instance_id ||
      (reveal.port_id && (selection.kind !== 'variable' || selection.port_id !== reveal.port_id))
    ) {
      revealing.current = false;
      return;
    }
    const point = positions.get(reveal.instance_id);
    if (!point) return;
    autoFit.current = false;
    setZoom(1);
    const center = reveal.port_id
      ? (portCenters[reveal.instance_id + '/' + reveal.port_id] ?? pitch)
      : pitch / 2;
    setPan({
      x: availableWidth / 2 - point.x - nodeWidth / 2,
      y: Math.min(pitch, availableHeight / 2 - center) - point.y,
    });
    const frame = requestAnimationFrame(() => {
      const head = viewport.current?.querySelector<HTMLElement>(
        `[data-instance="${CSS.escape(reveal.instance_id)}"]`,
      );
      const element = reveal.port_id
        ? (head
            ?.closest('.hf-node')
            ?.querySelector<HTMLElement>(`[data-port="${CSS.escape(reveal.port_id)}"]`) ?? head)
        : head;
      viewport.current?.scrollTo(0, 0);
      element?.focus({ preventScroll: true });
    });
    return () => cancelAnimationFrame(frame);
  }, [reveal, availableWidth, availableHeight, nodeHeights, portCenters, selection]);
  const svgWidth = portContent ? width * zoom : availableWidth;
  const svgHeight = portContent ? height * zoom : availableHeight;
  return (
    <>
      <div className="hf-view-toolbar" role="group" aria-label="Graph view controls">
        <Button
          size="sm"
          disabled={zoom <= 0.25}
          onClick={() => changeZoom(Math.max(0.25, zoom - 0.25))}
        >
          Zoom out
        </Button>
        <span className="hf-mono" aria-label="Graph zoom" aria-live="polite">
          {Math.round(zoom * 100)}%
        </span>
        <Button
          size="sm"
          disabled={zoom >= 2.5}
          onClick={() => changeZoom(Math.min(2.5, zoom + 0.25))}
        >
          Zoom in
        </Button>
        {portContent && <><Button size="sm" onClick={() => changeZoom(Math.max(.25, Math.min(1, availableWidth / width)))}>Fit width</Button><Button size="sm" onClick={() => changeZoom(1)}>100%</Button></>}
        {!portContent && (
          <>
            <Button size="sm" onClick={fit}>
              Fit model
            </Button>
            <Button size="sm" disabled={selection.kind === 'none'} onClick={focus}>
              Focus selection
            </Button>
            <SectionHelp topic="graph" />
          </>
        )}
        {toolbarEnd && <div className="hf-view-toolbar__end">{toolbarEnd}</div>}
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
            revealing.current = false;
            autoFit.current = false;
            setPan((p) => ({
              x: p.x + (e.key === 'ArrowLeft' ? pitch : e.key === 'ArrowRight' ? -pitch : 0),
              y: p.y + (e.key === 'ArrowUp' ? pitch : e.key === 'ArrowDown' ? -pitch : 0),
            }));
          }}
          onPointerDown={(e) => {
            if (e.target === e.currentTarget || (e.target as Element).tagName === 'svg') {
              gesture.current = { x: e.clientX, y: e.clientY, origin: pan };
              revealing.current = false;
              autoFit.current = false;
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
            viewBox={`0 0 ${svgWidth} ${svgHeight}`}
            width={svgWidth}
            height={svgHeight}
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
            <g ref={content} transform={`translate(${pan.x} ${pan.y}) scale(${zoom})`}>
              {(portContent ? projection.groups : []).map((g, i) => {
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
                  from.y +
                  (portContent
                    ? portCenter
                    : (portCenters[g.source + '/' + g.links[0].source_ref.port_id] ??
                      portCenter + Math.max(0, sourceIndex) * portHeight));
                const endY =
                  to.y +
                  (portContent
                    ? portCenter
                    : (portCenters[g.target + '/' + g.links[0].target_ref.port_id] ??
                      portCenter + Math.max(0, targetIndex) * portHeight));
                const feedback = to.y < from.y || (to.y === from.y && to.x <= from.x);
                const lane = pitch / 2 + ((i % 3) * pitch) / 3;
                const vertical = to.y > from.y && to.x === from.x;
                const bypass = !portContent && to.y === from.y && to.x - from.x > columnWidth + 1;
                const routeTop = Math.min(from.y, to.y) - lane;
                const sourceHeight = nodeHeights[g.source] ?? pitch * 8;
                const adjacent =
                  portContent &&
                  vertical &&
                  Math.abs(to.y - from.y - sourceHeight - pitch * 1.5) < 1;
                const labelX = bypass
                  ? (x + end) / 2
                  : adjacent
                    ? from.x + nodeWidth / 2 + pitch / 2
                    : vertical
                      ? portContent
                        ? width - pitch / 2
                        : x + pitch * 1.5
                      : (x + end) / 2;
                const labelY = bypass
                  ? routeTop - pitch / 6
                  : adjacent
                    ? (from.y + sourceHeight + to.y) / 2
                    : (y + endY) / 2 - pitch / 4;
                const d = adjacent
                  ? `M${from.x + nodeWidth / 2},${from.y + sourceHeight} V${to.y}`
                  : portContent
                    ? to.y === from.y && to.x > from.x
                      ? to.x - from.x <= columnWidth + 1
                        ? `M${x},${y} H${end}`
                        : `M${x},${y} H${x + pitch / 3} V${from.y - pitch / 3} ` +
                          `H${end - pitch / 3} V${endY} H${end}`
                      : `M${x},${y} H${width - pitch / 3 - ((i % 3) * pitch) / 8} ` +
                        `V${endY} H${to.x + nodeWidth}`
                    : bypass
                      ? `M${x},${y} H${x + pitch / 3} V${routeTop} ` +
                        `H${end - pitch / 3} V${endY} H${end}`
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
              {routes.map(({ link, d, label, feedback, start, end }) => {
                const active =
                  selection.kind === 'connection' && selection.connection_id === link.connection_id;
                const highlighted =
                  hovered === link.connection_id || focused === link.connection_id;
                const select = () =>
                  onSelect({ kind: 'connection', connection_id: link.connection_id });
                return (
                  <g
                    key={link.connection_id}
                    role="button"
                    tabIndex={0}
                    className={[
                      'graph-exchange hf-model-route',
                      feedback && 'feedback',
                      active && 'selected',
                      highlighted && 'highlighted',
                      trace.links.has(link.connection_id) && 'traced',
                    ]
                      .filter(Boolean)
                      .join(' ')}
                    data-connection={link.connection_id}
                    aria-label={label}
                    aria-pressed={active}
                    onPointerMove={(event) =>
                      setHovered(nearestRoute(event.clientX, event.clientY))
                    }
                    onPointerLeave={() => setHovered('')}
                    onFocus={() => setFocused(link.connection_id)}
                    onBlur={() => setFocused('')}
                    onClick={(event) => {
                      const connection_id = nearestRoute(event.clientX, event.clientY);
                      if (connection_id) onSelect({ kind: 'connection', connection_id });
                    }}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        select();
                      }
                    }}
                  >
                    <title>
                      {label}
                      {feedback ? ' · feedback' : ''}
                    </title>
                    <path d={d} className="exchange-hit" />
                    <path d={d} markerEnd={`url(#${marker})`} />
                    <circle className="hf-route-output" cx={start.x} cy={start.y} r={3} />
                    <circle className="hf-route-input" cx={end.x} cy={end.y} r={3} />
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
                      height={
                        portContent
                          ? (nodeHeights[instance.instance_id] ?? pitch * 8)
                          : (nodeHeights[instance.instance_id] ??
                            portHeight * ports.length + pitch * 2)
                      }
                    >
                      <ModelNode
                        className={portContent ? 'hf-node--explorer' : 'hf-node--model'}
                        name={instance.name}
                        index={portContent ? undefined : index + 1}
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
                          highlighted: endpointActive(instance.instance_id, port.port_id),
                          relationship: routes
                            .filter(({ link }) =>
                              [link.source_ref, link.target_ref].some(
                                (ref) =>
                                  ref.instance_id === instance.instance_id &&
                                  ref.port_id === port.port_id,
                              ),
                            )
                            .map((route) => route.label)
                            .join('; '),
                          state:
                            port.direction === 'input'
                              ? isFree(projection, instance.instance_id, port.port_id)
                                ? 'free'
                                : 'connected'
                              : routes.some(
                                    ({ link }) =>
                                      link.source_ref.instance_id === instance.instance_id &&
                                      link.source_ref.port_id === port.port_id,
                                  )
                                ? 'connected'
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
