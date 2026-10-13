import { SourceSurface } from './design';
import { Button, TextArea } from './design';
import { useRef, useState, type RefObject } from 'react';

type Props = { value: string; onChange: (value: string) => void; codeRef: RefObject<HTMLTextAreaElement | null>; error: boolean };

export function SourceEditor({ value, onChange, codeRef, error }: Props) {
  const [expanded, setExpanded] = useState(false), [notice, setNotice] = useState('');
  const expand = useRef<HTMLButtonElement>(null);
  // HTML textarea display normalizes line endings. Never feed display text back
  // to source ownership unless the engineer deliberately changes the text.
  const display = value.replace(/\r\n?/g, '\n');
  function toggleExpanded() {
    setExpanded(!expanded);
    // Narrow layouts return to their chosen projection. Keep focus on its
    // visible Inspector tab when collapsing would otherwise hide this button.
    if (expanded) requestAnimationFrame(() => {
      if (expand.current?.offsetParent === null) {
        const label = codeRef.current?.closest('[role="tabpanel"]')?.getAttribute('aria-labelledby');
        if (label) document.getElementById(label)?.focus();
      }
    });
  }
  return <div className={`source-editor${expanded ? ' expanded' : ''}`}>
    <p>Compute outputs from inputs. Set input values in a configuration.</p>
    <div role="group" aria-label="Source actions" className="source-actions">
      <Button ref={expand} type="button" aria-expanded={expanded} onClick={toggleExpanded}>{expanded ? 'Collapse source' : 'Expand source'}</Button>
    </div>
    <label htmlFor="python-source">Python source</label>
    <SourceSurface display={display} codeRef={codeRef}>
      <TextArea id="python-source" ref={codeRef} value={value} spellCheck={false} autoCapitalize="off" autoCorrect="off" wrap="off" aria-describedby={error ? 'model-errors code-help' : 'code-help'}
        onKeyDown={e => { if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); expand.current?.focus(); } }}
        onChange={e => { onChange(e.target.value); setNotice('Text edited: the next save uses UTF-8 text with LF line endings.'); }} />
    </SourceSurface>
    <p id="code-help" className="sr-only">Tab leaves source. Escape focuses source actions. Save previews changes and never executes source.</p>
    <p className="source-notice" aria-live="polite">{notice}</p>

  </div>;
}
