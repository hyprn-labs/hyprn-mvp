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

/** Recovery instructions follow admitted API actions, never a guessed retry. */
function assistantProblem(error: string, canResume: boolean, canStop: boolean) {
  const diagnostics: Record<string, string> = {
    access_lost: 'Study access ended. No further changes will be made.',
    assistant_disabled: 'Assistant access is turned off.',
    provider_authentication: 'The server’s Assistant credential needs updating.',
    provider_access: 'Assistant provider access is unavailable for this account.',
    provider_rate_limit: 'The provider’s rate limit was reached.',
    provider_billing_error: 'The Assistant provider account needs credits.',
    assistant_internal_error: 'An application error interrupted the Assistant.',
    provider_response_too_large:
      'A document response was too large for the Assistant connection to process.',
    provider_resume_delivery_unknown: 'The previous Resume could not be confirmed.',
    provider_attachment_too_large: 'A document exceeds the supported attachment size.',
    invalid_provider_attachment: 'A document attachment could not be read safely.',
    user_allowance_exhausted: 'Your cumulative $20 Assistant allowance has been used.',
    user_allowance_unknown: 'Spending could not be verified.',
    provider_budget_reached: 'The Assistant allowance needs review before work can continue.',
    shared_allowance_exhausted: 'The shared Assistant allowance has been used.',
    shared_allowance_unknown: 'Assistant availability could not be confirmed.',
    shared_allowance_busy: 'Another study is still active. Your message is saved.',
    message_delivery_unknown:
      'Message delivery could not be confirmed. It has not been sent again.',
    session_delivery_unknown:
      'Session creation could not be confirmed. No replacement was started.',
    tool_outcome_unknown: 'An operation could not be confirmed. It has not been repeated.',
    provider_unavailable: 'The connection to the Assistant provider was interrupted.',
    turn_time_limit: 'The Assistant reached this turn’s time limit.',
  };
  const applicationProblem = ['provider_response_too_large', 'assistant_internal_error'].includes(
    error,
  );
  const label = applicationProblem ? 'Application problem' : 'Assistant paused';
  const cause = diagnostics[error] ?? 'The Assistant encountered an application problem.';
  const sourceProblem = ['provider_attachment_too_large', 'invalid_provider_attachment'].includes(
    error,
  );
  const next = canResume
    ? 'Select Resume to continue.'
    : sourceProblem && canStop
      ? 'Select Stop. Once stopped, request a smaller or different source.'
      : 'Recovery is unavailable here. Contact your application administrator.';
  return { label, detail: `${cause} Your conversation and saved work are preserved. ${next}` };
}

/** Backend lifecycle only: no fabricated percentages, timers or scientific outcomes. */
export function AssistantActivity({
  state,
  detail,
  error,
  canResume = false,
  canStop = false,
}: {
  state: 'queued' | 'starting' | 'running' | 'waiting' | 'stopping' | 'blocked';
  detail?: string;
  error?: string | null;
  canResume?: boolean;
  canStop?: boolean;
}) {
  const stages = {
    queued: ['Queued', 'Your message is saved. Waiting for available Assistant capacity.'],
    starting: ['Starting', 'Connecting this study’s session.'],
    running: ['Working', 'The Assistant is processing your request.'],
    waiting: ['Waiting for calculations', 'Submitted calculations are still running.'],
    stopping: ['Stopping', 'Waiting for the Assistant to confirm the stop.'],
    blocked: ['Assistant paused', 'Your conversation is saved.'],
  } as const;
  const [stageLabel, explanation] = stages[state];
  const problem =
    state === 'blocked' ? assistantProblem(error ?? 'unknown', canResume, canStop) : null;
  const label = problem?.label ?? stageLabel;
  return (
    <section
      className="hf-assistant-activity"
      role={state === 'blocked' ? 'alert' : 'status'}
      aria-live="polite"
      aria-atomic="true"
      data-state={state}
    >
      <StatusTag tone={state === 'blocked' ? 'warning' : 'inert'}>{label}</StatusTag>
      <p>{detail ?? problem?.detail ?? explanation}</p>
    </section>
  );
}
