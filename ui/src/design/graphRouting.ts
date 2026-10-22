import type { Projection } from '../GraphView';

type Point = { x: number; y: number };

/** Round only within each orthogonal segment's clearance, never across a card corner. */
function rounded(points: Point[], radius: number) {
  let path = `M${points[0].x},${points[0].y}`;
  for (let i = 1; i < points.length - 1; i++) {
    const a = points[i - 1],
      b = points[i],
      c = points[i + 1];
    const before = Math.hypot(b.x - a.x, b.y - a.y);
    const after = Math.hypot(c.x - b.x, c.y - b.y);
    if (!before || !after) continue;
    const r = Math.min(radius, before / 2, after / 2);
    const start = { x: b.x + ((a.x - b.x) * r) / before, y: b.y + ((a.y - b.y) * r) / before };
    const end = { x: b.x + ((c.x - b.x) * r) / after, y: b.y + ((c.y - b.y) * r) / after };
    path += ` L${start.x},${start.y} Q${b.x},${b.y} ${end.x},${end.y}`;
  }
  const end = points[points.length - 1];
  return path + ` L${end.x},${end.y}`;
}

/** Model grid only. Vertical lanes stay in column gutters; bypass/feedback lanes
 * stay above all cards. The explorer owns its independent measured layout. */
export function modelRoutes(
  projection: Projection,
  positions: Map<string, Point>,
  centers: Record<string, number>,
  nodeWidth: number,
  gap: number,
  rowHeight: number,
  firstPort: number,
) {
  const links = projection.groups
    .flatMap((group) => group.links)
    .sort((a, b) => a.connection_id.localeCompare(b.connection_id));
  const top = Math.min(...[...positions.values()].map((p) => p.y));
  const endpoints = links.map((link) => {
    const source = projection.nodes.find(
      (n) => n.instance.instance_id === link.source_ref.instance_id,
    )!;
    const target = projection.nodes.find(
      (n) => n.instance.instance_id === link.target_ref.instance_id,
    )!;
    const from = positions.get(source.instance.instance_id)!;
    const to = positions.get(target.instance.instance_id)!;
    const center = (id: string, port: string, ports: typeof source.ports) =>
      centers[id + '/' + port] ??
      firstPort +
        Math.max(
          0,
          ports.findIndex((p) => p.port_id === port),
        ) *
          rowHeight;
    const start = {
      x: from.x + nodeWidth,
      y: from.y + center(source.instance.instance_id, link.source_ref.port_id, source.ports),
    };
    const end = {
      x: to.x,
      y: to.y + center(target.instance.instance_id, link.target_ref.port_id, target.ports),
    };
    return { link, source, target, from, to, start, end };
  });
  return endpoints.map(({ link, source, target, from, to, start, end }, index) => {
    const offset = gap / 6 + ((index + 1) * gap) / (3 * (links.length + 1));
    const adjacent = from.y === to.y && Math.abs(to.x - from.x - nodeWidth - gap) < 1;
    // Opposite horizontal legs at the same height could overlap in a gutter.
    // Keep those routes on separate outer lanes, even when their rounded ends hide
    // the overlap at one zoom. Identical source references may share an initial leg.
    const equal = (a: number, b: number) => Math.abs(a - b) < 1;
    const conflict = endpoints.some((other) => {
      if (other.link.connection_id === link.connection_id) return false;
      const sameSource =
        other.link.source_ref.instance_id === link.source_ref.instance_id &&
        other.link.source_ref.port_id === link.source_ref.port_id;
      return (
        (equal(other.start.x, start.x) &&
          (equal(other.start.y, end.y) || (!sameSource && equal(other.start.y, start.y)))) ||
        (equal(other.end.x, end.x) && (equal(other.end.y, start.y) || equal(other.end.y, end.y)))
      );
    });
    const lane = top - gap / 3 - (index * gap) / 6;
    const points =
      adjacent && !conflict
        ? equal(start.y, end.y)
          ? [start, end]
          : [start, { x: start.x + offset, y: start.y }, { x: start.x + offset, y: end.y }, end]
        : [
            start,
            { x: start.x + offset, y: start.y },
            { x: start.x + offset, y: lane },
            { x: end.x - offset, y: lane },
            { x: end.x - offset, y: end.y },
            end,
          ];
    const output = source.ports.find((p) => p.port_id === link.source_ref.port_id)!;
    const input = target.ports.find((p) => p.port_id === link.target_ref.port_id)!;
    return {
      link,
      start,
      end,
      d: rounded(points, gap / 12),
      feedback: to.y < from.y || (to.y === from.y && to.x <= from.x),
      label:
        `Output ${source.instance.name} · ${output.code_symbol} ` +
        `to Input ${target.instance.name} · ${input.code_symbol}`,
    };
  });
}
