import type { ComponentPropsWithoutRef, ReactNode } from 'react';

type BoxProps = ComponentPropsWithoutRef<'div'>;
type SectionProps = ComponentPropsWithoutRef<'section'>;

/** Layout only: callers own statements, source resolution and immutable identities. */
export function Assertion({
  statement,
  children,
  className = '',
  ...props
}: ComponentPropsWithoutRef<'article'> & { statement?: ReactNode }) {
  return (
    <article {...props} className={'hf-assertion ' + className}>
      {statement != null && <p className="hf-assertion__statement">{statement}</p>}
      {children}
    </article>
  );
}

export function AssertionList({ className = '', ...props }: BoxProps) {
  return <div {...props} className={'hf-assertions ' + className} />;
}

/** Empty source collections add neither a visible wrapper nor phantom spacing. */
export function EvidenceStack({ className = '', ...props }: BoxProps) {
  return <div {...props} className={'hf-evidence-stack ' + className} />;
}

export function ReadingSection({ className = '', ...props }: SectionProps) {
  return <section {...props} className={'hf-reading-section ' + className} />;
}

export function ReadingStack({ className = '', ...props }: BoxProps) {
  return <div {...props} className={'hf-reading-stack ' + className} />;
}

export function ActionGroup({
  align = 'start',
  className = '',
  ...props
}: BoxProps & { align?: 'start' | 'end' }) {
  return <div {...props} className={`hf-actions hf-actions--${align} ${className}`} />;
}
