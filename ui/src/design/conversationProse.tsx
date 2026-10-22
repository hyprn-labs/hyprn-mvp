import { Fragment, type ReactNode } from 'react';
import { OpenLink } from './navigation';

/** Small, safe Markdown vocabulary for untrusted messages. HTML is always text. */
function inline(text: string, depth = 0): ReactNode {
  if (depth > 3) return text;
  const pattern = /(`[^`\n]+`|\*\*[^*\n]+\*\*|__[^_\n]+__|\*[^*\n]+\*|\[[^\]\n]+\]\([^\s)]+\))/g;
  const nodes: ReactNode[] = [];
  let end = 0;
  for (const match of text.matchAll(pattern)) {
    nodes.push(text.slice(end, match.index));
    const token = match[0];
    const link = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(token);
    let node: ReactNode = token;
    if (token.startsWith('`')) node = <code>{token.slice(1, -1)}</code>;
    else if (token.startsWith('**') || token.startsWith('__'))
      node = <strong>{inline(token.slice(2, -2), depth + 1)}</strong>;
    else if (token.startsWith('*')) node = <em>{inline(token.slice(1, -1), depth + 1)}</em>;
    else if (link && /^https?:\/\//i.test(link[2]))
      node = (
        <OpenLink href={link[2]} target="_blank" rel="noopener noreferrer">
          {link[1]}
        </OpenLink>
      );
    nodes.push(<Fragment key={match.index}>{node}</Fragment>);
    end = match.index + token.length;
  }
  nodes.push(text.slice(end));
  return nodes;
}
const cells = (line: string) =>
  line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split(/(?<!\\)\|/)
    .map((s) => s.trim().replace(/\\\|/g, '|'));
const tableRule = (line: string) => cells(line).every((c) => /^:?-{3,}:?$/.test(c));
const listItem = (line: string) => /^\s*(?:([-*+])|\d+[.)])\s+(.+)$/.exec(line);

export function ConversationProse({ text }: { text: string }) {
  const lines = text.split(/\r?\n/);
  const blocks: ReactNode[] = [];
  for (let i = 0; i < lines.length;) {
    const line = lines[i];
    if (!line.trim()) {
      i++;
      continue;
    }
    const key = i;
    if (/^\s*```/.test(line)) {
      const code: string[] = [];
      for (i++; i < lines.length && !/^\s*```/.test(lines[i]); i++) code.push(lines[i]);
      if (i < lines.length) i++;
      blocks.push(
        <pre key={key}>
          <code>{code.join('\n')}</code>
        </pre>,
      );
      continue;
    }
    const heading = /^#{1,6}\s+(.+?)\s*#*$/.exec(line);
    if (heading) {
      blocks.push(<h3 key={key}>{inline(heading[1])}</h3>);
      i++;
      continue;
    }
    if (line.includes('|') && i + 1 < lines.length && tableRule(lines[i + 1])) {
      const headers = cells(line),
        rows: string[][] = [];
      i += 2;
      while (i < lines.length && lines[i].includes('|') && lines[i].trim())
        rows.push(cells(lines[i++]));
      blocks.push(
        <div
          className="hf-conversation-table"
          key={key}
          tabIndex={0}
          role="region"
          aria-label="Message table"
        >
          <table>
            <thead>
              <tr>
                {headers.map((h, n) => (
                  <th scope="col" key={n}>
                    {inline(h)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, r) => (
                <tr key={r}>
                  {headers.map((_, c) => (
                    <td key={c}>{inline(row[c] ?? '')}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      continue;
    }
    const item = listItem(line);
    if (item) {
      const ordered = !item[1],
        items: ReactNode[] = [];
      while (i < lines.length) {
        const next = listItem(lines[i]);
        if (!next || !next[1] !== ordered) break;
        items.push(<li key={i}>{inline(next[2])}</li>);
        i++;
      }
      blocks.push(ordered ? <ol key={key}>{items}</ol> : <ul key={key}>{items}</ul>);
      continue;
    }
    const paragraph = [line];
    i++;
    while (
      i < lines.length &&
      lines[i].trim() &&
      !listItem(lines[i]) &&
      !/^\s*(#{1,6}\s|```)/.test(lines[i]) &&
      !(lines[i].includes('|') && i + 1 < lines.length && tableRule(lines[i + 1]))
    ) {
      paragraph.push(lines[i++]);
    }
    blocks.push(<p key={key}>{inline(paragraph.join(' '))}</p>);
  }
  return <div className="hf-conversation-prose">{blocks}</div>;
}
