import { unitLabel } from './unitLabels';
import type { ModelPackage, Source } from './contract';
import { project, type Snapshot } from './GraphView';
import { variableRows, type VariableContext } from './VariablesTable';
import type { Selection } from './workspaceModel';

export type ExportScope = { snapshot: Snapshot; values: VariableContext; configuration?: string; run?: string; selection: Selection; unsaved: boolean };
export const escapeMarkup = (value: string) => value.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]!));
export function csvCell(value: string | number) {
  const raw = typeof value === 'number' ? String(value) : (/^[\u0000-\u0020]*[=+@-]|^[\t\r\n]/.test(value) ? "'" + value : value);
  return '"' + raw.replaceAll('"', '""') + '"';
}
export function downloadBytes(raw: BlobPart, name: string, type: string) {
  const url = URL.createObjectURL(new Blob([raw], { type })), link = document.createElement('a');
  link.href = url; link.download = name; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export const sha256 = async (bytes: Uint8Array) => Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes as Uint8Array<ArrayBuffer>)), b => b.toString(16).padStart(2, '0')).join('');
export async function exactSource(source: Source) {
  const bytes = Uint8Array.from(atob(source.bytes), c => c.charCodeAt(0));
  if (await sha256(bytes) !== source.sha256) throw new Error('Source hash mismatch. No download was created.');
  return bytes as Uint8Array<ArrayBuffer>;
}
export function canonical(value: unknown): string {
  if (value === null || typeof value !== 'object') { const text = JSON.stringify(value); if (text === undefined || typeof value === 'number' && !Number.isFinite(value)) throw new Error('Invalid JSON value.'); return text; }
  if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
  return '{' + Object.keys(value).sort().map(key => JSON.stringify(key) + ':' + canonical((value as Record<string, unknown>)[key])).join(',') + '}';
}
export async function checkPackage(text: string): Promise<ModelPackage> {
  if (new TextEncoder().encode(text).length > 2 * 1024 * 1024 - 512) throw new Error('The portable model record exceeds the 2 MiB limit.');
  const value = JSON.parse(text);
  const invalid = (message = 'Unsupported or invalid portable model record.'): never => { throw new Error(message); };
  const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
  const hash = /^[0-9a-f]{64}$/;
  function bounded(node: unknown, depth = 0) {
    if (depth > 32) invalid('The portable model record is nested too deeply.');
    if (node && typeof node === 'object') {
      if (Array.isArray(node) && node.length > 10000) invalid('A list in the portable model record has too many items.');
      Object.values(node).forEach(child => bounded(child, depth + 1));
    }
  }
  bounded(value);
  if (!value || !['1', '2', '3', '4'].includes(value.schema_version) || !Array.isArray(value.revisions) || !value.revisions.length || value.revisions.length > 1000 || !Array.isArray(value.files) || value.files.length > 1000 || !Array.isArray(value.required_capabilities) || value.required_capabilities.some((v: unknown) => typeof v !== 'string')) invalid();
  if (value.schema_version === '3' && !value.required_capabilities.includes('unit_declarations/1')) invalid('Record format 3 requires unit_declarations/1.');
  if (value.schema_version === '4' && !value.required_capabilities.includes('quantity_definitions/1')) invalid('Record format 4 requires quantity_definitions/1.');
  if (!uuid.test(value.model_id) || !uuid.test(value.model_revision_id)) invalid('The portable model record has invalid identities.');
  const { digest, ...body } = value;
  if (!hash.test(digest) || await sha256(new TextEncoder().encode(canonical(body))) !== digest) invalid('The portable model record does not match its SHA-256. No import was submitted.');
  const inventory = new Map<string, ModelPackage['files'][number]>();
  async function addFile(path: string, raw: Uint8Array, media_type: string, role: 'source' | 'model') {
    const key = (await sha256(new TextEncoder().encode('model-package-v1:' + path))).slice(0, 32);
    const file_id = [key.slice(0, 8), key.slice(8, 12), key.slice(12, 16), key.slice(16, 20), key.slice(20)].join('-');
    inventory.set(path, { file_id, path, size: raw.length, sha256: await sha256(raw), media_type, role });
  }
  const seen = new Set<string>(); let parent: string | null = null;
  for (const revision of value.revisions) {
    if (!revision || !(value.schema_version === '1' ? ['1'] : value.schema_version === '2' ? ['1', '2'] : value.schema_version === '3' ? ['1', '2', '3'] : ['1', '2', '3', '4']).includes(revision.schema_version)) invalid('Model version record formats do not match the portable model record format.');
    if (revision.schema_version === '3' && (!Array.isArray(revision.required_capabilities) || !revision.required_capabilities.includes('unit_declarations/1'))) invalid('Model version record format 3 requires unit_declarations/1.');
    const { digest: expected, ...content } = revision;
    if (revision.model_id !== value.model_id || !uuid.test(revision.model_revision_id) || seen.has(revision.model_revision_id) || revision.parent_model_revision_id !== parent || !Array.isArray(revision.source_files) || revision.source_files.length > 1000 || !hash.test(expected) || await sha256(new TextEncoder().encode(canonical(content))) !== expected) invalid('Model version identity, parent or SHA-256 mismatch.');
    for (const field of ['definitions', 'instances', 'ports', 'connections', 'boundary_mappings', 'annotations']) if (!Array.isArray(revision[field]) || revision[field].length > 1000) invalid('Invalid or oversized model collection.');
    if (revision.instances.length + revision.connections.length + revision.definitions.reduce((n: number, d: { ports: unknown[] }) => n + (Array.isArray(d.ports) ? d.ports.length : 1001), 0) > 1000) invalid('Model exceeds the 1000 element limit.');
    if (revision.schema_version === '4') {
      if (!Array.isArray(revision.required_capabilities) || !revision.required_capabilities.includes('quantity_definitions/1')) invalid('Model version record format 4 requires quantity_definitions/1.');
      const definitions=new Set<string>();
      for (const definition of revision.definitions) {
        if (!definition || !uuid.test(definition.definition_version_id) || definitions.has(definition.definition_version_id) || !Array.isArray(definition.ports)) invalid('Invalid component definition version.');
        definitions.add(definition.definition_version_id);
        const ports=new Set<string>(),kinds=new Set<string>();
        for (const port of definition.ports) {
          if (!port || !uuid.test(port.port_id) || ports.has(port.port_id) || port.definition_version_id!==definition.definition_version_id) invalid('Invalid component definition port.');
          ports.add(port.port_id);kinds.add(typeof port.units);
          if(typeof port.units!=='string'){
            const units=port.units;
            if(!units||!['unspecified','dimensionless','physical'].includes(units.kind)||Object.keys(units).some(key=>key!=='kind'&&(units.kind!=='physical'||key!=='expression'))||units.kind==='physical'&&(typeof units.expression!=='string'||!units.expression.trim()||units.expression.length>256)) invalid('Invalid typed unit declaration.');
          }
        }
        if(kinds.size>1)invalid('A definition must preserve one unit representation.');
        if('quantity_definitions' in definition){
          if(!Array.isArray(definition.quantity_definitions)||definition.quantity_definitions.length>1000)invalid('Invalid quantity definitions.');
          const described=new Set<string>();
          for(const quantity of definition.quantity_definitions){
            if(!quantity||Object.keys(quantity).some(key=>!['port_id','statement'].includes(key))||!ports.has(quantity.port_id)||described.has(quantity.port_id)||typeof quantity.statement!=='string'||!quantity.statement.trim()||quantity.statement.length>4096)invalid('Invalid quantity definition.');
            described.add(quantity.port_id);
          }
        }
      }
      if(revision.instances.some((instance:{definition_version_id:string})=>!definitions.has(instance.definition_version_id)))invalid('Instance references an unavailable definition version.');
      if(canonical(revision.ports)!==canonical(revision.definitions.flatMap((definition:{ports:unknown[]})=>definition.ports)))invalid('Model ports differ from their component definition versions.');
      if(revision.ports.some((port:{units:unknown})=>typeof port.units!=='string')&&!revision.required_capabilities.includes('unit_declarations/1'))invalid('Typed ports require unit_declarations/1.');
    }
    await addFile('revisions/' + revision.model_revision_id + '.json', new TextEncoder().encode(canonical(revision)), 'application/json', 'model');
    seen.add(revision.model_revision_id); parent = revision.model_revision_id;
    if (revision.schema_version === '1' && 'assumptions' in revision || (['2','3','4'].includes(revision.schema_version)) && (!Array.isArray(revision.assumptions) || revision.assumptions.length > 1000)) invalid('Invalid model version assumptions.');
    const ids = new Set<string>();
    for (const item of revision.assumptions ?? []) {
      if (!item || !uuid.test(item.assumption_id) || ids.has(item.assumption_id) || typeof item.statement !== 'string' || !item.statement.trim() || item.statement.length > 4096 || !Array.isArray(item.evidence_links) || item.evidence_links.length > 64) invalid('Invalid assumption.');
      ids.add(item.assumption_id);
      if (!item.owner || !(item.owner.kind === 'model' || item.owner.kind === 'instance' && uuid.test(item.owner.instance_id) && item.owner.instance_id !== revision.root_instance_id && revision.instances?.some((i: { instance_id: string }) => i.instance_id === item.owner.instance_id))) invalid('Invalid assumption owner.');
      const links = new Set<string>();
      for (const link of item.evidence_links) { const key = link?.evidence_version_id + '/' + link?.relation; if (!link || !uuid.test(link.evidence_version_id) || !['supports', 'challenges', 'context'].includes(link.relation) || links.has(key)) invalid('Invalid assumption citation.'); links.add(key); }
    }
    for (const source of revision.source_files) {
      if (!source || source.encoding !== 'base64' || source.media_type !== 'text/x-python' || !hash.test(source.sha256) || typeof source.bytes !== 'string' || source.bytes.length > 349528 || !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(source.bytes)) invalid('Invalid or oversized source.');
      const raw = await exactSource(source); if (raw.length > 256 * 1024) invalid('Source exceeds the 256 KiB bound.'); await addFile('sources/' + source.sha256 + '.py', raw, 'text/x-python', 'source');
    }
  }
  const selected = value.revisions[value.revisions.length - 1];
  if (parent !== value.model_revision_id || selected.schema_version !== value.schema_version) invalid('The selected model version must be the last version in the portable model record.');
  const fileIds = new Set<string>(), paths = new Set<string>(); let total = 0;
  for (const file of value.files) {
    if (!file || !uuid.test(file.file_id) || fileIds.has(file.file_id) || typeof file.path !== 'string' || !file.path || file.path.length > 4096 || file.path.startsWith('/') || file.path.includes('\\') || file.path.split('/').some((part: string) => !part || part === '.' || part === '..') || paths.has(file.path) || !Number.isSafeInteger(file.size) || file.size < 0 || !hash.test(file.sha256)) invalid('Invalid file list in the portable model record.');
    fileIds.add(file.file_id); paths.add(file.path); total += file.size;
    if (total > 32 * 1024 * 1024) invalid('The files in the portable model record exceed the size limit.');
  }
  if (canonical(value.files) !== canonical([...inventory.values()].sort((a, b) => a.path < b.path ? -1 : a.path > b.path ? 1 : 0))) invalid("The portable model record's file list does not match its model versions and source files.");
  return value as ModelPackage; // Server performs closed-schema, capability, topology and collision validation atomically.
}
const visible = (element: Element) => !element.closest('[hidden]') && element.getClientRects().length > 0 && getComputedStyle(element).visibility !== 'hidden';
function workbench(root: HTMLElement) { const region = [...root.querySelectorAll<HTMLElement>('.connected-views')].find(visible); if (!region) throw new Error("Open a model or a run's Model tab first."); return region; }
function controls(root: Element) {
  return [...root.querySelectorAll<HTMLInputElement | HTMLSelectElement>('input, select')].filter(e => e.closest('.variable-filters, .projection-controls, .variable-split')).map(e => `${e.closest('label')?.childNodes[0]?.textContent?.trim() || e.getAttribute('aria-label') || 'Filter'}=${e instanceof HTMLInputElement && e.type === 'checkbox' ? e.checked : e.value}`).join('; ');
}
export function scopeLines(scope: ExportScope) {
  return [`Model ${scope.snapshot.model_id}`, 'model_revision_id' in scope.snapshot ? `Model version ${scope.snapshot.model_revision_id} · SHA-256 ${scope.snapshot.digest}` : `Model draft revision ${scope.snapshot.draft_revision}`,
    `Configuration ${scope.configuration ?? (scope.values.kind === 'configuration_draft' ? 'unsaved explicit input proposal' : 'none')} · Run ${scope.run ?? 'none'}`,
    `Selection ${JSON.stringify(scope.selection)}`, scope.unsaved ? 'Unsaved edits exist; the model and source come from the loaded saved state. Displayed configuration input proposals are labeled separately.' : 'Authorized loaded state; no recomputation.'];
}
export function variablesCsv(root: HTMLElement, scope: ExportScope) {
  const region = workbench(root), table = region.querySelector<HTMLTableElement>('table[aria-label="Quantities"]');
  if (!table || !visible(table)) throw new Error('Open the model view before exporting its displayed quantities.');
  const all = variableRows(scope.snapshot, project(scope.snapshot), scope.values), lookup = new Map(all.map(r => [r.key, r]));
  const rows = [...table.querySelectorAll<HTMLTableRowElement>('tbody tr[data-variable]')].map(tr => { const row = lookup.get(tr.dataset.variable!); if (!row) throw new Error('Displayed row does not belong to this snapshot.'); return row; });
  // The export keeps its established columns: the displayed rows and filters select the
  // scope; the canonical table folds connections into Direction but the CSV keeps them separate.
  const headers = ['Variable', 'Component', 'Direction', 'Definition', 'Units', 'Connections', ...(scope.values.kind === 'model' ? [] : ['Value', 'Provenance'])];
  const endpoint = (id: { instance_id: string; port_id: string }) => `${id.instance_id}/${id.port_id}`;
  // The projection uses an empty display fallback; presence comes only from
  // the exact recorded/proposed value, never from its model declaration.
  const valueUnits = (r: typeof all[number]) => {
    const context = scope.values, matches = (item: { target: { instance_id: string; port_id: string } }) => endpoint(item.target) === r.key;
    if (context.kind === 'configuration_draft' && r.availability !== 'explicit') return 'Not recorded';
    const record = context.kind === 'run' && r.port.direction === 'output' ? context.history.results?.outputs.find(matches)
      : context.kind === 'run' ? context.history.configuration?.inputs.find(matches)
      : context.kind === 'configuration' ? context.configuration.inputs.find(matches)
      : context.kind === 'configuration_draft' ? context.inputs.find(matches) : undefined;
    return record?.units === undefined ? 'Not recorded' : unitLabel(record.units);
  };
  const data = rows.map(r => headers.map(header => {
    switch (header) {
      case 'Variable': return r.port.name === r.port.code_symbol ? r.port.code_symbol : `${r.port.code_symbol} (${r.port.name})`; case 'Component': return r.instance.name; case 'Direction': return r.port.direction;
      case 'Definition': return r.definition ?? 'No definition'; // same wording as the displayed cell
      case 'Connections': case 'Connected from/to': return [...r.incoming.map(c => `Producer ${endpoint(c.source_ref)}`), ...r.outgoing.map(c => `Consumer ${endpoint(c.target_ref)}`)].join('; ') || 'Unconnected';
      case 'Units': return unitLabel(r.port.units); case 'Value': case 'Value/status': return ['available', 'explicit'].includes(r.availability) && Number.isFinite(Number(r.value)) ? Number(r.value) : r.value;
      case 'Provenance': return r.provenance || 'No provenance specified'; case 'symbol': return r.port.code_symbol; case 'version': return r.instance.definition_version_id; case 'type': return r.port.value_type;
      case 'diagnostics': return r.availability === 'unavailable' ? r.provenance : r.availability; default: throw new Error('Unsupported displayed column.');
    }
  }).concat([valueUnits(r), r.key]));
  return [...scopeLines(scope).map(line => [line]), [`Displayed scope: ${rows.length} of ${all.length} loaded variables; filtered rows only`], [`Filters: ${controls(region)}`], [...headers, 'Value units', 'Instance/port identity'], ...data].map(row => row.map(csvCell).join(',')).join('\r\n') + '\r\n';
}
const ns = 'http://www.w3.org/2000/svg';
function svgElement(name: string, attrs: Record<string, string | number> = {}, text?: string) { const e = document.createElementNS(ns, name); for (const [key, value] of Object.entries(attrs)) e.setAttribute(key, String(value)); if (text !== undefined) e.textContent = text; return e; }
function textLines(text: string, length: number) { return text.match(new RegExp(`.{1,${length}}`, 'gu')) ?? ['']; }
function label(parent: Element, text: string, x: number, y: number, length = 90) { const lines = textLines(text.replace(/[\r\n]+/g, ' '), length); lines.forEach((line, i) => parent.append(svgElement('text', { x, y: y + i * 19, fill: '#17212b', 'font-size': 14, 'font-family': 'sans-serif' }, line))); return lines.length; }
function graphSvg(source: SVGSVGElement) {
  const measure = document.createElement('canvas').getContext('2d');
  if (!measure) throw new Error('Diagram text measurement is unavailable.');
  measure.font = '14px sans-serif';
  function slotLabel(element: Element) {
    const text = element.textContent ?? '', x = Number(element.getAttribute('x')), y = Number(element.getAttribute('y'));
    const width = Number(element.getAttribute('width')), height = Number(element.getAttribute('height'));
    // Keep the live Graph's rectangle and full metadata; no label can paint into a neighboring slot.
    const slot = svgElement('svg', { x, y, width, height, viewBox: `${x} ${y} ${width} ${height}`, overflow: 'hidden' });
    slot.append(svgElement('title', {}, text));
    let remaining = Array.from(text.replace(/[\r\n]+/g, ' '));
    const limit = Math.min(2, Math.max(0, Math.floor((height - 20) / 19) + 1));
    for (let line = 0; line < limit && remaining.length; line++) {
      const suffix = line === limit - 1 && measure!.measureText(remaining.join('')).width > width - 4 ? '…' : '';
      let low = 0, high = remaining.length;
      while (low < high) { const mid = Math.ceil((low + high) / 2); if (measure!.measureText(remaining.slice(0, mid).join('') + suffix).width <= width - 4) low = mid; else high = mid - 1; }
      slot.append(svgElement('text', { x: x + 2, y: y + 17 + line * 19, fill: '#17212b', 'font-size': 14, 'font-family': 'sans-serif' }, remaining.slice(0, low).join('') + suffix));
      remaining = remaining.slice(low);
    }
    return slot;
  }
  const allowed = new Set(['svg', 'defs', 'marker', 'path', 'g', 'rect', 'text', 'tspan', 'title', 'line', 'polyline', 'polygon', 'circle']);
  const attrs = new Set(['viewBox', 'x', 'y', 'width', 'height', 'rx', 'd', 'transform', 'points', 'x1', 'x2', 'y1', 'y2', 'cx', 'cy', 'r', 'id', 'markerWidth', 'markerHeight', 'markerUnits', 'refX', 'refY', 'orient', 'marker-end', 'dy', 'text-anchor']);
  function copy(element: Element): Element | null {
    if (element.localName === 'foreignObject') {
      const card = element.querySelector<HTMLElement>('.hf-node');
      if (!card) return slotLabel(element);
      // A Foundry card owns sibling controls. Retain every visible slot in the
      // inert export, using measured geometry rather than flattening the card.
      const host = element.getBoundingClientRect(), box = card.getBoundingClientRect();
      const x = Number(element.getAttribute('x')), y = Number(element.getAttribute('y'));
      const scale = Number(element.getAttribute('width')) / host.width;
      const group = svgElement('g');
      group.append(svgElement('rect', { x, y, width: box.width * scale, height: box.height * scale,
        rx: parseFloat(getComputedStyle(card).borderRadius), fill: getComputedStyle(card).backgroundColor,
        stroke: getComputedStyle(card).borderColor }));
      for (const control of card.querySelectorAll<HTMLElement>('button')) {
        const row = control.getBoundingClientRect();
        const slot = svgElement('foreignObject', { x: x + (row.x - host.x) * scale,
          y: y + (row.y - host.y) * scale, width: row.width * scale, height: row.height * scale }, control.textContent ?? '');
        group.append(slotLabel(slot));
      }
      return group;
    }
    if (!allowed.has(element.localName)) return null;
    const next = svgElement(element.localName);
    for (const a of element.attributes) if (attrs.has(a.name) && (!a.value.includes('url(') || /^url\(#[A-Za-z0-9_-]+\)$/.test(a.value))) next.setAttribute(a.name, a.value);
    const css = getComputedStyle(element);
    for (const property of ['fill', 'stroke', 'stroke-width', 'stroke-linejoin', 'stroke-dasharray', 'paint-order', 'text-anchor', 'font-size', 'font-weight', 'opacity']) { const value = css.getPropertyValue(property); if (value && !/url\(|[<>]/i.test(value)) next.setAttribute(property, value); }
    next.setAttribute('font-family', 'sans-serif');
    for (const node of element.childNodes) { if (node.nodeType === Node.TEXT_NODE) next.append(document.createTextNode(node.textContent ?? '')); else if (node instanceof Element) { const child = copy(node); if (child) next.append(child); } }
    return next;
  }
  return copy(source) as SVGSVGElement;
}
export function diagramSvg(root: HTMLElement, scope: ExportScope) {
  const region = workbench(root), selected = region.querySelector('[role="tab"][aria-selected="true"]')?.textContent;
  let body: Element, width: number, height: number;
  if (selected === 'Graph') {
    const graph = region.querySelector<SVGSVGElement>('svg.connected-graph'); if (!graph || !visible(graph)) throw new Error('No visible Graph is available.');
    body = graphSvg(graph); const box = graph.viewBox.baseVal; width = box.width; height = box.height;
    body.setAttribute('width', String(width)); body.setAttribute('height', String(height));
  } else if (selected === 'XDSM') {
    const table = region.querySelector('table.xdsm'); if (!table || !visible(table)) throw new Error('No visible XDSM is available.');
    const rows = [...table.querySelectorAll('tr')].map(tr => [...tr.children].map(td => (td as HTMLElement).innerText));
    if (rows.reduce((n, row) => n + row.length, 0) > 40000) throw new Error('XDSM export exceeds 40,000 cells. Export the displayed quantities as CSV instead.');
    width = Math.max(860, Math.max(...rows.map(row => row.length)) * 220); body = svgElement('g'); let y = 0;
    for (const row of rows) { const size = Math.max(48, ...row.map(cell => textLines(cell.replace(/[\r\n]+/g, ' '), 27).length * 19 + 20)); row.forEach((cell, i) => { body.append(svgElement('rect', { x: i * 220, y, width: 220, height: size, fill: '#fff', stroke: '#718096' })); label(body, cell, i * 220 + 8, y + 22, 27); }); y += size; } height = y;
  } else throw new Error('Open Graph or XDSM before exporting the visible diagram. Hidden projections are not exported.');
  const info = [...scopeLines(scope), `${selected}: ${project(scope.snapshot).nodes.length} visible / ${project(scope.snapshot).nodes.length} loaded components; ${scope.snapshot.connections.length} links. Units appear in the Quantities table; diagram port labels are symbols.`, `Filters/presentation: ${controls(region)}. Search highlights matches; it does not remove components.`, 'Diagram presentation only; no numerical computation.'];
  const svg = svgElement('svg', { viewBox: `0 0 ${width} 1`, width, role: 'img' }); let caption = 24;
  for (const line of info) caption += label(svg, line, 12, caption, Math.max(40, Math.floor((width - 24) / 8))) * 19;
  caption += 16; const group = svgElement('g', { transform: `translate(0 ${caption})` }); group.append(body); svg.append(group);
  svg.setAttribute('height', String(height + caption)); svg.setAttribute('viewBox', `0 0 ${width} ${height + caption}`);
  svg.prepend(svgElement('rect', { width, height: height + caption, fill: '#fff' }));
  return { text: new XMLSerializer().serializeToString(svg), width, height: height + caption };
}
export async function diagramPng(svg: ReturnType<typeof diagramSvg>) {
  if (svg.width > 8192 || svg.height > 8192 || svg.width * svg.height > 16_000_000) throw new Error('PNG exceeds the 8192-pixel or 16-megapixel bound. Use SVG for this scope.');
  const url = URL.createObjectURL(new Blob([svg.text], { type: 'image/svg+xml' }));
  try { const image = new Image(); image.src = url; await image.decode(); const canvas = document.createElement('canvas'); canvas.width = svg.width; canvas.height = svg.height; const context = canvas.getContext('2d'); if (!context) throw new Error('PNG rendering is unavailable.'); context.drawImage(image, 0, 0); return await new Promise<Blob>((resolve, reject) => canvas.toBlob(blob => blob ? resolve(blob) : reject(new Error('PNG rendering failed.')), 'image/png')); } finally { URL.revokeObjectURL(url); }
}
export function diagramHtml(svg: string) { return `<!doctype html><html lang="en"><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"><title>HYPRN MVP read-only diagram</title><style>body{font:16px sans-serif;color:#17212b;background:white;margin:24px}svg{max-width:100%;height:auto}</style><h1>Read-only engineering diagram</h1><p>The model state and displayed scope are identified below. This file contains no executable source or external assets.</p>${svg}</html>`; }
