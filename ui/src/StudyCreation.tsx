import { useEffect, useRef, useState } from 'react';
import type { HyprnMvpApi } from './api';
import { completeStudyStart, studyStart, type StudyStart } from './assistantStudyStart';
import { Button, FormActions, FormField, TextArea, TextInput, ToggleField } from './design';

/** One creation form and public command sequence for the canvas and Assistant. */
export function StudyCreation({
  api,
  onOpen,
  onCancel,
}: {
  api: HyprnMvpApi;
  onOpen: (id: string) => void;
  onCancel: () => void;
}) {
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const [question, setQuestion] = useState('');
  const [autonomous, setAutonomous] = useState(false);
  const attempt = useRef<StudyStart | null>(null);
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function create() {
    if (busy || !name.trim() || !question.trim() || api.pending) return;
    const fence = api.fence({});
    setBusy(true);
    setError('');
    try {
      const start = attempt.current ?? studyStart(name.trim(), question.trim(), autonomous);
      attempt.current = start;
      const studyId = await completeStudyStart(api, start);
      if (fence.valid() && mounted.current) {
        setName('');
        setQuestion('');
        setAutonomous(false);
        attempt.current = null;
        onOpen(studyId);
      }
    } catch (cause) {
      const failed = await api.readFailed(cause, fence, { command: true });
      if (failed !== 'stale' && mounted.current)
        setError(
          attempt.current?.studyId
            ? 'The study is saved. Setup is not yet confirmed; retry to continue the same study.'
            : 'Could not confirm study creation. Review the pending operation before retrying.',
        );
    } finally {
      fence.done();
      if (mounted.current) setBusy(false);
    }
  }
  return (
    <>
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
        <FormActions
          primary={
            <Button
              type="submit"
              variant="primary"
              disabled={busy || !name.trim() || !question.trim() || !!api.pending}
            >
              {busy ? 'Preparing…' : attempt.current ? 'Continue setup' : 'Create study'}
            </Button>
          }
        >
          <Button
            disabled={busy || (!!attempt.current && !attempt.current.studyId)}
            onClick={() => {
              const id = attempt.current?.studyId;
              attempt.current = null;
              if (id) onOpen(id);
              else onCancel();
            }}
          >
            {attempt.current?.studyId ? 'Open study' : 'Cancel'}
          </Button>
        </FormActions>
      </form>
      {error && <p role="alert">{error}</p>}
    </>
  );
}
