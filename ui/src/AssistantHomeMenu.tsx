import { useEffect, useState } from 'react';
import { StudyCreation } from './StudyCreation';
import type { HyprnMvpApi } from './api';
import { ActionGroup, Button, FormField, Select } from './design';

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
  const [studies, setStudies] = useState<{ study_id: string; name: string }[]>([]);
  const [selected, setSelected] = useState('');
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
        <StudyCreation
          api={api}
          onOpen={(id) => {
            setMode('chat');
            onOpen(id);
          }}
          onCancel={() => setMode('chat')}
        />
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
