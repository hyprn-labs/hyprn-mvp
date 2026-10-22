import { useId, type ReactNode } from 'react';
import { StatusTag } from './components';
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

/** Backend lifecycle only: no fabricated percentages, timers or scientific outcomes. */
export function AssistantActivity({
  state,
  detail,
}: {
  state: 'queued' | 'starting' | 'running' | 'waiting' | 'stopping' | 'blocked';
  detail?: string;
}) {
  const stages = {
    queued: ['Queued', 'Your message is saved. Waiting for available Assistant capacity.'],
    starting: ['Starting', 'Connecting this study’s session.'],
    running: ['Working', 'The Assistant is processing your request.'],
    waiting: ['Waiting for calculations', 'Submitted calculations are still running.'],
    stopping: ['Stopping', 'Waiting for the Assistant to confirm the stop.'],
    blocked: ['Needs attention', 'Your conversation is saved.'],
  } as const;
  const [label, explanation] = stages[state];
  return (
    <section
      className="hf-assistant-activity"
      role={state === 'blocked' ? 'alert' : 'status'}
      aria-live="polite"
      aria-atomic="true"
      data-state={state}
    >
      <StatusTag tone={state === 'blocked' ? 'warning' : 'inert'}>{label}</StatusTag>
      <p>{detail ?? explanation}</p>
    </section>
  );
}
