import { AssistantHomeMenu } from './AssistantHomeMenu';
import { useEffect, useRef, useState } from 'react';
import type { AssistantConversationRead3, HyprnMvpApi } from './api';
import { ApiError } from './api';
import {
  ActionGroup,
  AssistantActivity,
  AssistantComposer,
  AssistantPane,
  Button,
  ConversationLog,
  ConversationMessage,
  TextArea,
} from './design';

const diagnostics: Record<string, string> = {
  access_lost: 'Study access ended. No further changes will be made.',
  assistant_disabled: 'Assistant access is turned off.',
  provider_authentication: 'The server’s Claude credential needs updating.',
  provider_access: 'Claude access is unavailable for this account.',
  provider_rate_limit: 'Claude’s rate limit was reached. The request has been preserved.',
  provider_billing_error:
    'The provider account needs credits. Add credits to the configured Anthropic account, then send a new message.',
  assistant_internal_error:
    'The Assistant was interrupted. Saved work is preserved. Resume to continue.',
  user_allowance_exhausted:
    'Your cumulative $20 Assistant allowance has been used. Saved work is preserved.',
  user_allowance_unknown:
    'Spending could not be verified. Resume when the connection is available.',
  provider_budget_reached: 'The Assistant allowance needs review before work can continue.',
  shared_allowance_exhausted: 'The shared Assistant allowance has been used.',
  shared_allowance_unknown:
    'Assistant availability could not be confirmed. Server review is needed.',
  shared_allowance_busy: 'Another study is still active. Your message is saved.',
  message_delivery_unknown: 'Message delivery is being reviewed. It has not been sent again.',
  session_delivery_unknown: 'Session creation needs review. No replacement session was started.',
  tool_outcome_unknown: 'An operation needs review. It has not been repeated.',
  provider_unavailable: 'The connection to Claude was interrupted. Your conversation is saved.',
  turn_time_limit: 'The assistant reached this turn’s time limit.',
};

export function StudyAssistant({
  api,
  studyId,
  studyName,
  home,
  onOpenStudy,
  expanded,
  onToggleExpanded,
  onClose,
}: {
  api: HyprnMvpApi;
  studyId?: string;
  studyName?: string;
  home: boolean;
  onOpenStudy: (id: string) => void;
  expanded: boolean;
  onToggleExpanded: () => void;
  onClose: () => void;
}) {
  const [conversation, setConversation] = useState<AssistantConversationRead3 | null>(null);
  const [homeMode, setHomeMode] = useState<'chat' | 'create' | 'switch'>('chat');
  const choosingStudy = home && homeMode !== 'chat';
  const [draft, setDraft] = useState('');
  const [error, setError] = useState('');
  const [sending, setSending] = useState(false);
  const pending = useRef<{ command_id: string; text: string } | null>(null);
  const lifetime = useRef(0);

  useEffect(() => {
    const generation = ++lifetime.current;
    const fence = api.fence({ studyId });
    let timer: ReturnType<typeof setTimeout>;
    let closed = false;
    setConversation(null);
    setDraft('');
    setError('');
    pending.current = null;
    const off = api.onSessionChange(() => {
      if (!fence.valid()) {
        setConversation(null);
        setDraft('');
        pending.current = null;
        setError('Study access is no longer available.');
      }
    });
    async function poll() {
      if (!studyId || closed || !fence.valid()) return;
      try {
        const value = await api.assistant(studyId, fence.signal);
        if (!closed && fence.valid() && lifetime.current === generation) {
          setConversation(value);
          if (
            pending.current &&
            value.messages.some((m) => m.message_id === pending.current?.command_id)
          ) {
            pending.current = null;
            setDraft('');
            setError('');
          }
        }
      } catch (cause) {
        const failure = await api.readFailed(cause, fence);
        if (closed || failure === 'stale') return;
        if (failure === 'access-lost') setConversation(null);
        setError(
          failure === 'access-lost'
            ? 'Study access is no longer available.'
            : 'Could not refresh the conversation.',
        );
      }
      if (!closed && fence.valid()) timer = setTimeout(poll, 1500);
    }
    void poll();
    return () => {
      closed = true;
      clearTimeout(timer);
      fence.abort();
      fence.done();
      off();
    };
  }, [api, studyId]);

  async function send() {
    if (!studyId || sending || !draft.trim() || (!pending.current && !conversation?.can_send))
      return;
    const generation = lifetime.current;
    const fence = api.fence({ studyId });
    const command = pending.current ?? { command_id: crypto.randomUUID(), text: draft };
    pending.current = command;
    setSending(true);
    setError('');
    try {
      const value = await api.assistantSend(studyId, command);
      if (fence.valid() && lifetime.current === generation) {
        setConversation(value);
        pending.current = null;
        setDraft('');
      }
    } catch (cause) {
      await api.readFailed(cause, fence, { command: true });
      if (fence.valid() && lifetime.current === generation) {
        if (cause instanceof ApiError && cause.detail.outcome === 'unchanged') {
          // A definite rejection did not admit a turn: keep the draft editable.
          // Only uncertain delivery keeps the original command locked for reconciliation.
          pending.current = null;
          const explanation = cause.detail.fields.map((field) => field.message).join(' ');
          setError(
            explanation || 'The message was not sent. Your draft is kept. ' + cause.detail.message,
          );
        } else {
          setError('Could not confirm delivery. The same message is retained for retry.');
        }
      }
    } finally {
      fence.done();
      if (lifetime.current === generation) setSending(false);
    }
  }

  async function stop(resume = false) {
    if (!studyId) return;
    const generation = lifetime.current;
    const fence = api.fence({ studyId });
    try {
      const value = await (resume ? api.assistantResume(studyId) : api.assistantStop(studyId));
      if (fence.valid() && lifetime.current === generation) setConversation(value);
    } catch (cause) {
      await api.readFailed(cause, fence, { command: true });
      if (fence.valid() && lifetime.current === generation)
        setError(
          resume
            ? 'Could not confirm Resume. Refresh before trying again.'
            : 'Could not confirm Stop. Try again.',
        );
    } finally {
      fence.done();
    }
  }

  const unavailable = !studyId || conversation?.state === 'unavailable';
  const activity =
    conversation && !['idle', 'unavailable'].includes(conversation.state)
      ? (conversation.state as
          'queued' | 'starting' | 'running' | 'waiting' | 'stopping' | 'blocked')
      : null;
  return (
    <AssistantPane
      state="connected"
      context={
        choosingStudy ? null : studyId ? (
          <>
            Study: <strong>{studyName ?? 'Loading study…'}</strong>
          </>
        ) : (
          'No study attached'
        )
      }
      navigation={
        home && (
          <AssistantHomeMenu api={api} mode={homeMode} onMode={setHomeMode} onOpen={onOpenStudy} />
        )
      }
      expanded={expanded}
      onToggleExpanded={onToggleExpanded}
      onClose={onClose}
      actions={
        studyId && !choosingStudy ? (
          <AssistantComposer>
            <TextArea
              aria-label="Message assistant"
              placeholder="Ask about this study…"
              rows={3}
              value={draft}
              maxLength={16384}
              disabled={unavailable || sending || !!pending.current}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (
                  event.key === 'Enter' &&
                  !event.shiftKey &&
                  !event.nativeEvent.isComposing &&
                  event.keyCode !== 229
                ) {
                  event.preventDefault();
                  if (!event.repeat) void send();
                }
              }}
            />
            <ActionGroup align="end">
              {conversation?.can_stop && (
                <Button variant="secondary" onClick={() => void stop()}>
                  Stop
                </Button>
              )}
              {conversation?.can_resume ? (
                <Button variant="primary" onClick={() => void stop(true)}>
                  Resume
                </Button>
              ) : (
                <Button
                  variant="primary"
                  disabled={
                    unavailable ||
                    sending ||
                    (!pending.current && !conversation?.can_send) ||
                    !draft.trim()
                  }
                  onClick={() => void send()}
                >
                  {sending ? 'Sending…' : pending.current ? 'Retry send' : 'Send'}
                </Button>
              )}
            </ActionGroup>
          </AssistantComposer>
        ) : undefined
      }
    >
      {!choosingStudy && (
        <ConversationLog>
          {studyId && unavailable && (
            <p>The assistant is not configured for this installation yet.</p>
          )}
          {conversation?.has_earlier_messages && <p>Showing the latest messages.</p>}
          {conversation?.messages.map((message) => (
            <ConversationMessage
              key={message.message_id}
              role={message.role}
              text={message.text}
              authorDisplayName={message.author_display_name}
            />
          ))}
          {activity && (
            <AssistantActivity
              state={activity}
              detail={
                conversation?.error
                  ? (diagnostics[conversation.error] ??
                    'An operation needs review. Your conversation is saved.')
                  : undefined
              }
            />
          )}
          {error && <p role="alert">{error}</p>}
        </ConversationLog>
      )}
    </AssistantPane>
  );
}
