import { createPortal } from 'react-dom';
import { AssistantHomeMenu } from './AssistantHomeMenu';
import { useEffect, useRef, useState } from 'react';
import type { AssistantConversationRead4, HyprnMvpApi } from './api';
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
  onStudyChanged,
  container,
  expanded,
  onToggleExpanded,
  onClose,
}: {
  api: HyprnMvpApi;
  studyId?: string;
  studyName?: string;
  home: boolean;
  onOpenStudy: (id: string) => void;
  onStudyChanged: (studyId: string) => void;
  container: HTMLElement | null;
  expanded: boolean;
  onToggleExpanded: () => void;
  onClose: () => void;
}) {
  const [conversation, setConversation] = useState<AssistantConversationRead4 | null>(null);
  const [homeMode, setHomeMode] = useState<'chat' | 'create' | 'switch'>('chat');
  const choosingStudy = home && homeMode !== 'chat';
  const [draft, setDraft] = useState('');
  const [error, setError] = useState('');
  const [sending, setSending] = useState(false);
  const pending = useRef<{ command_id: string; text: string } | null>(null);
  const lifetime = useRef(0);
  const commands = useRef(0);
  const cursor = useRef<string | null>(null);
  const wake = useRef<() => void>(() => {});
  const [loadingEarlier, setLoadingEarlier] = useState(false);

  const latestChange = useRef(onStudyChanged);
  latestChange.current = onStudyChanged;
  const visible = useRef(!!container);
  visible.current = !!container;
  const observed = useRef<{ state: string; cursor: string | null } | null>(null);
  const invalidated = useRef(false);
  useEffect(() => { if (container) wake.current(); }, [container]);

  function accept(value: AssistantConversationRead4, earlier = false) {
    if (!earlier) {
      const previous = observed.current;
      const settled = ['idle', 'blocked', 'unavailable'].includes(value.state);
      if (settled && (
        (previous && !['idle', 'blocked', 'unavailable'].includes(previous.state)) ||
        (value.messages.some((item) => item.role === 'assistant') &&
          previous?.cursor !== value.next_cursor)
      )) invalidated.current = true;
      // Catch-up pages describe one settled turn, not separate authoring changes.
      if (studyId && settled && !value.has_more_messages && invalidated.current) {
        invalidated.current = false;
        latestChange.current(studyId);
      }
      observed.current = { state: value.state, cursor: value.next_cursor };
      cursor.current = value.next_cursor;
    }
    setConversation((previous) => {
      if (!previous) return value;
      const ordered = earlier
        ? [...value.messages, ...previous.messages]
        : [...previous.messages, ...value.messages];
      const messages = [...new Map(ordered.map((item) => [item.message_id, item])).values()];
      return {
        ...(earlier ? previous : value),
        messages,
        next_cursor: earlier ? previous.next_cursor : value.next_cursor,
        earlier_cursor: earlier ? value.earlier_cursor : previous.earlier_cursor,
        has_earlier_messages: earlier ? value.has_earlier_messages : previous.has_earlier_messages,
      };
    });
  }

  useEffect(() => {
    const generation = ++lifetime.current;
    const fence = api.fence({ studyId });
    let timer: ReturnType<typeof setTimeout>;
    let closed = false;
    let polling = false;
    let delay = 1500;
    cursor.current = null;
    observed.current = null;
    invalidated.current = false;
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
      if (!studyId || closed || polling || !fence.valid() || document.hidden) return;
      polling = true;
      const commandGeneration = commands.current;
      try {
        const value = await api.assistant(
          studyId,
          fence.signal,
          cursor.current ? { after: cursor.current } : {},
        );
        if (
          !closed &&
          fence.valid() &&
          lifetime.current === generation &&
          commands.current === commandGeneration
        ) {
          accept(value);
          delay = value.has_more_messages
            ? 0
            : ['idle', 'blocked', 'unavailable'].includes(value.state)
              ? 15000
              : 1500;
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
        if (commands.current === commandGeneration || failure === 'access-lost') {
          if (failure === 'access-lost') setConversation(null);
          delay = Math.min(30000, Math.max(3000, delay * 2));
          setError(
            failure === 'access-lost'
              ? 'Study access is no longer available.'
              : 'Could not refresh the conversation.',
          );
        }
      } finally {
        polling = false;
      }
      if (!closed && fence.valid() && (visible.current || invalidated.current ||
          !['idle', 'blocked', 'unavailable'].includes(observed.current?.state ?? 'idle')))
        timer = setTimeout(poll, delay);
    }
    const refresh = () => {
      clearTimeout(timer);
      void poll();
    };
    wake.current = refresh;
    document.addEventListener('visibilitychange', refresh);
    void poll();
    return () => {
      document.removeEventListener('visibilitychange', refresh);
      wake.current = () => {};
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
        commands.current += 1;
        accept(value);
        wake.current();
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
      if (fence.valid() && lifetime.current === generation) {
        commands.current += 1;
        accept(value);
        wake.current();
      }
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

  async function earlier() {
    if (!studyId || !conversation?.earlier_cursor || loadingEarlier) return;
    const generation = lifetime.current;
    const fence = api.fence({ studyId });
    setLoadingEarlier(true);
    try {
      const value = await api.assistant(studyId, fence.signal, {
        before: conversation.earlier_cursor,
      });
      if (fence.valid() && lifetime.current === generation) accept(value, true);
    } catch (cause) {
      await api.readFailed(cause, fence);
      if (fence.valid() && lifetime.current === generation)
        setError('Could not load earlier messages.');
    } finally {
      fence.done();
      if (lifetime.current === generation) setLoadingEarlier(false);
    }
  }

  const unavailable = !studyId || conversation?.state === 'unavailable';
  const activity =
    conversation && !['idle', 'unavailable'].includes(conversation.state)
      ? (conversation.state as
          'queued' | 'starting' | 'running' | 'waiting' | 'stopping' | 'blocked')
      : null;
  if (!container) return null;
  return createPortal(
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
          {conversation?.has_earlier_messages && (
            <Button variant="secondary" disabled={loadingEarlier} onClick={() => void earlier()}>
              {loadingEarlier ? 'Loading…' : 'Earlier messages'}
            </Button>
          )}
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
    </AssistantPane>,
    container,
  );
}
