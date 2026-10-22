import type { ReactNode } from 'react';

type Passage = { reference: string; location?: string; excerpt?: string };

/** Source text is supplied by its author or document citation, never inferred from a note. */
export function EvidenceReading({
  excerpt,
  reference,
  location,
  explanation,
  attribution,
  assistant = false,
  references = [],
  passages,
}: {
  excerpt?: string;
  reference?: string;
  location?: string;
  explanation: string;
  attribution?: ReactNode;
  assistant?: boolean;
  references?: string[];
  passages?: Passage[];
}) {
  const sources = passages?.length
    ? passages
    : reference || excerpt
      ? [{ reference: reference ?? '', location, excerpt }]
      : [];
  const additional = [...new Set(references)].filter(
    (value) => !sources.some((source) => source.reference === value),
  );
  const label = sources.length
    ? assistant
      ? 'Assistant explanation'
      : 'Explanation'
    : 'Evidence note';
  return (
    <div className="hf-evidence-reading">
      {sources.map((source, index) => (
        <div className="hf-evidence-reading__source" key={index}>
          {source.reference && (
            <section aria-label="Source">
              <p className="hf-evidence-reading__label">Source</p>
              <p className="hf-evidence-reading__text">{source.reference}</p>
            </section>
          )}
          {source.excerpt && (
            <section className="hf-evidence-passage" aria-label="Source excerpt">
              <div className="hf-evidence-reading__heading">
                <p className="hf-evidence-reading__label">Source excerpt</p>
                {source.location && (
                  <p className="hf-evidence-reading__location">{source.location}</p>
                )}
              </div>
              <blockquote>{source.excerpt}</blockquote>
            </section>
          )}
          {!source.excerpt && source.location && (
            <p className="hf-evidence-reading__location">{source.location}</p>
          )}
        </div>
      ))}
      {additional.length > 0 && (
        <section aria-label="Source references">
          <p className="hf-evidence-reading__label">Source{additional.length > 1 ? 's' : ''}</p>
          {additional.map((source) => (
            <p className="hf-evidence-reading__text" key={source}>
              {source}
            </p>
          ))}
        </section>
      )}
      <section aria-label={label}>
        <p className="hf-evidence-reading__label">{label}</p>
        {attribution}
        <p className="hf-evidence-reading__text">{explanation}</p>
      </section>
    </div>
  );
}
