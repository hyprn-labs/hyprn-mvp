import type { AnchorHTMLAttributes, ButtonHTMLAttributes, ReactNode, Ref } from 'react';
import { ActionIcon } from './icons';

type Presentation = {
  size?: 'sm' | 'desk' | 'floor';
  direction?: 'open' | 'back';
  className?: string;
} & (
  | { iconOnly: true; 'aria-label': string; children?: never }
  | { iconOnly?: false; children: ReactNode }
);
export type OpenLinkProps = Presentation &
  (
    | ({ href: string; ref?: Ref<HTMLAnchorElement> } & Omit<
        AnchorHTMLAttributes<HTMLAnchorElement>,
        'children' | 'className'
      >)
    | ({ href?: never; ref?: Ref<HTMLButtonElement> } & Omit<
        ButtonHTMLAttributes<HTMLButtonElement>,
        'children' | 'className' | 'type'
      >)
  );

/** One opening target: a named reader link or the arrow beside a passive fact. */
export function OpenLink({
  children,
  iconOnly = false,
  direction = 'open',
  size = 'desk',
  className = '',
  ...props
}: OpenLinkProps) {
  const classes =
    `hf-btn hf-btn--quiet hf-btn--${size} hf-open-link${iconOnly ? ' hf-btn--icon' : ''} ${className}`.trim();
  const arrow = (
    <span className="hf-icon">
      <ActionIcon name={direction === 'back' ? 'back' : 'open-record'} />
    </span>
  );
  const content = (
    <>
      {direction === 'back' && arrow}
      {!iconOnly && <span className="hf-open-link__label">{children}</span>}
      {direction === 'open' && arrow}
    </>
  );
  if (props.href !== undefined) {
    const { href, ...anchor } = props;
    return (
      <a {...(anchor as AnchorHTMLAttributes<HTMLAnchorElement>)} href={href} className={classes}>
        {content}
      </a>
    );
  }
  return (
    <button
      {...(props as ButtonHTMLAttributes<HTMLButtonElement>)}
      type="button"
      className={classes}
    >
      {content}
    </button>
  );
}
