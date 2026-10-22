import { SourceSurface } from './design';
import { TextArea } from './design';
import { useState, type RefObject } from 'react';

type Props = {
  value: string;
  onChange: (value: string) => void;
  codeRef: RefObject<HTMLTextAreaElement | null>;
  error: boolean;
};

export function SourceEditor({ value, onChange, codeRef, error }: Props) {
  const [notice, setNotice] = useState('');
  // HTML textarea display normalizes line endings. Never feed display text back
  // to source ownership unless the engineer deliberately changes the text.
  const display = value.replace(/\r\n?/g, '\n');
  return (
    <div className="source-editor">
      <label htmlFor="python-source">Python source</label>
      <SourceSurface display={display} codeRef={codeRef}>
        <TextArea
          id="python-source"
          ref={codeRef}
          value={value}
          spellCheck={false}
          autoCapitalize="off"
          autoCorrect="off"
          wrap="off"
          aria-describedby={error ? 'model-errors code-help' : 'code-help'}
          onChange={(e) => {
            onChange(e.target.value);
            setNotice('Text edited: the next save uses UTF-8 text with LF line endings.');
          }}
        />
      </SourceSurface>
      <p id="code-help" className="sr-only">
        Tab leaves source. Save previews changes and never executes source.
      </p>
      <p className="source-notice" aria-live="polite">
        {notice}
      </p>
    </div>
  );
}
