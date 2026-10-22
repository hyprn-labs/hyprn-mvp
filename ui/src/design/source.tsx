import { useLayoutEffect, useMemo, useRef, type ReactNode, type RefObject } from 'react';
// A display aid, not a parser or Python validator. React escapes every token.
function highlight(text: string) {
  const tokens = /#[^\n]*|"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*'|\b(?:False|None|True|and|as|assert|async|await|break|class|continue|def|del|elif|else|except|finally|for|from|global|if|import|in|is|lambda|nonlocal|not|or|pass|raise|return|try|while|with|yield)\b|\b\d+(?:\.\d+)?\b/g;
  const parts = []; let end = 0;
  for (const match of text.matchAll(tokens)) {
    const start = match.index!; parts.push(text.slice(end, start));
    const word = match[0]; const kind = word[0] === '#' ? 'comment' : /["']/.test(word[0]) ? 'string' : /^\d/.test(word) ? 'number' : 'keyword';
    parts.push(<span className={`source-${kind}`} key={start}>{word}</span>); end = start + word.length;
  }
  parts.push(text.slice(end), '\n'); return parts;
}


/** Inert display only. Neither scrolling nor highlighting modifies the owned bytes. */
export function SourceSurface({ display, codeRef, children }: { display: string; codeRef: RefObject<HTMLTextAreaElement | null>; children: ReactNode }) {
  const gutter = useRef<HTMLDivElement>(null), highlightView = useRef<HTMLDivElement>(null);
  const colored = useMemo(() => highlight(display), [display]);
  useLayoutEffect(() => {
    const editor = codeRef.current;
    if (!editor) return;
    const sync = () => {
      if (gutter.current) gutter.current.scrollTop = editor.scrollTop;
      if (highlightView.current) { highlightView.current.scrollTop = editor.scrollTop; highlightView.current.scrollLeft = editor.scrollLeft; }
    };
    editor.addEventListener('scroll', sync); sync();
    return () => editor.removeEventListener('scroll', sync);
  }, [codeRef, display]);
  return <div className="source-frame">
    <div ref={gutter} className="source-gutter" aria-hidden="true"><pre className="source-line-numbers">{display.split('\n').map((_, i) => i + 1).join('\n')}</pre></div>
    <div className="source-area"><div ref={highlightView} aria-hidden="true" className="source-highlight-scroll"><pre className="source-highlight">{colored}</pre></div>{children}</div>
  </div>;
}

/** Verified source reads as a full-width document; never as an action group. */
export function SourceReader({ identity, text }: { identity: ReactNode; text: string }) {
  return <div className="hf-source-reader">{identity}<pre tabIndex={0} aria-label="Read-only authored source">{text}</pre></div>;
}
