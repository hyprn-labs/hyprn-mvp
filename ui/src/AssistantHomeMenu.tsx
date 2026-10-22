import { useEffect, useRef, useState } from 'react';
import { completeStudyStart, studyStart, type StudyStart } from './assistantStudyStart';
import type { HyprnMvpApi } from './api';
import { ActionGroup, Button, FormField, Select, TextInput, TextArea, ToggleField } from './design';

/** Home chooses a study; it never sends an unscoped message to a provider. */
export function AssistantHomeMenu({
  api,
  onOpen,
  mode,
  onMode: setMode,
}: {
  api: HyprnMvpApi;
  mode: 'chat' | 'create' | 'switch';
  onMode: (mode: 'chat' | 'create' | 'switch') => void;
  onOpen: (id: string) => void;
}) {
  const [question, setQuestion] = useState('');
  const [autonomous, setAutonomous] = useState(false);
  const attempt = useRef<StudyStart | null>(null);
  const [name, setName] = useState('');
  const [studies, setStudies] = useState<{ study_id: string; name: string }[]>([]);
  const [selected, setSelected] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    if (mode !== 'switch') return;
    const fence = api.fence({});
    void api
      .studies()
      .then((value) => {
        if (fence.valid()) setStudies(value);
      })
      .catch(async (cause) => {
        const failed = await api.readFailed(cause, fence);
        if (failed !== 'stale') setError('Could not load studies.');
      });
    return () => {
      fence.abort();
      fence.done();
    };
  }, [api, mode]);
  async function create() {
    if (busy || !name.trim() || !question.trim() || api.pending) return;
    const fence = api.fence({});
    setBusy(true);
    setError('');
    try {
      const start = attempt.current ?? studyStart(name.trim(), question.trim(), autonomous);
      attempt.current = start;
      const studyId = await completeStudyStart(api, start);
      if (fence.valid()) {
        setMode('chat');
        setName('');
        setQuestion('');
        setAutonomous(false);
        attempt.current = null;
        onOpen(studyId);
      }
    } catch (cause) {
      const failed = await api.readFailed(cause, fence, { command: true });
      if (failed !== 'stale')
        setError(
          attempt.current?.studyId
            ? 'The study is saved. Setup is not yet confirmed; retry to continue the same study.'
            : 'Could not confirm study creation. Review the pending operation before retrying.',
        );
    } finally {
      fence.done();
      setBusy(false);
    }
  }
  return (
    <div className="hf-assistant-navigation">
      {mode === 'chat' && (
        <ActionGroup>
          <Button
            size="sm"
            onClick={() => {
              setMode('create');
              setError('');
            }}
          >
            Start a new study
          </Button>
          <Button
            size="sm"
            onClick={() => {
              setMode('switch');
              setError('');
            }}
          >
            Switch study
          </Button>
        </ActionGroup>
      )}
      {mode === 'create' && (
        <form
          className="hf-form-stack"
          onSubmit={(event) => {
            event.preventDefault();
            void create();
          }}
        >
          <FormField label="Study name">
            <TextInput
              value={name}
              maxLength={4096}
              required
              disabled={busy || !!attempt.current}
              onChange={(event) => setName(event.target.value)}
            />
          </FormField>
          <FormField label="Study question">
            <TextArea
              value={question}
              rows={4}
              maxLength={4096}
              required
              disabled={busy || !!attempt.current}
              onChange={(event) => setQuestion(event.target.value)}
            />
          </FormField>
          <ToggleField
            label="Autonomous agent"
            description="Complete the brief, run the study and prepare the answer."
            checked={autonomous}
            disabled={busy || !!attempt.current}
            onChange={setAutonomous}
          />
          <ActionGroup align="end">
            <Button
              disabled={busy || (!!attempt.current && !attempt.current.studyId)}
              onClick={() => {
                const id = attempt.current?.studyId;
                attempt.current = null;
                setMode('chat');
                if (id) onOpen(id);
              }}
            >
              {attempt.current?.studyId ? 'Open study' : 'Cancel'}
            </Button>
            <Button
              type="submit"
              variant="primary"
              disabled={busy || !name.trim() || !question.trim() || !!api.pending}
            >
              {busy ? 'Preparing…' : attempt.current ? 'Continue setup' : 'Create study'}
            </Button>
          </ActionGroup>
        </form>
      )}
      {mode === 'switch' && (
        <div className="hf-form-stack">
          <FormField label="Study">
            <Select value={selected} onChange={(event) => setSelected(event.target.value)}>
              <option value="">Select a study</option>
              {studies.map((study) => (
                <option key={study.study_id} value={study.study_id}>
                  {study.name}
                </option>
              ))}
            </Select>
          </FormField>
          <ActionGroup align="end">
            <Button onClick={() => setMode('chat')}>Cancel</Button>
            <Button
              variant="primary"
              disabled={!selected}
              onClick={() => {
                setMode('chat');
                onOpen(selected);
              }}
            >
              Open study
            </Button>
          </ActionGroup>
        </div>
      )}
      {error && <p role="alert">{error}</p>}
    </div>
  );
}
