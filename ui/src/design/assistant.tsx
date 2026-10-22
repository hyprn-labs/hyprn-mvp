import { useId, type ReactNode } from 'react';
import { ConversationProse } from './conversationProse';

/** Study conversations share readable prose, author labels and token-based separation. */
export function ConversationMessage({
  role,
  text,
  authorDisplayName,
}: {
  role: 'user' | 'assistant';
  text: string;
  authorDisplayName?: string | null;
}) {
  return (
    <article className="hf-conversation-message" data-role={role}>
      <strong>{role === 'user' ? authorDisplayName || 'User' : 'Assistant'}</strong>
      <ConversationProse text={text} />
    </article>
  );
}

export function ConversationLog({ children }: { children: ReactNode }) {
  return (
    <div className="hf-conversation-log" role="log" aria-label="Study conversation">
      {children}
    </div>
  );
}

export function AssistantComposer({ children }: { children: ReactNode }) {
  return <div className="hf-assistant-composer">{children}</div>;
}

/** An explicit opt-in: state is conveyed by word, thumb and colour. */
export function ToggleField({
  label,
  description,
  checked,
  disabled,
  onChange,
}: {
  label: string;
  description?: string;
  checked: boolean;
  disabled?: boolean;
  onChange: (checked: boolean) => void;
}) {
  const id = useId();
  return (
    <div className="hf-toggle-field">
      <span className="hf-toggle-field__text">
        <strong id={id}>{label}</strong>
        {description && <small id={`${id}-description`}>{description}</small>}
      </span>
      <button
        type="button"
        role="switch"
        className="hf-toggle"
        aria-labelledby={id}
        aria-describedby={description ? `${id}-description` : undefined}
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
      >
        {checked ? 'On' : 'Off'}
      </button>
    </div>
  );
}
