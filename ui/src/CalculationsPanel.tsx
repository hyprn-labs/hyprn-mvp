import { OpenLink, ReturnLink } from './design';
import { DialogActions } from './design';
import { AnalysisExecutionPanel } from './AnalysisExecutionPanel';
import { useCollectionRead } from './useCollectionRead';
import { CollectionStatus } from './design';
import { useId, useEffect, useState } from 'react';
import { message, type ConfigurationSummary1, type HyprnMvpApi } from './api';
import { scopeConfigurations, useStudyRead } from './calculationReads';
import type { CalculationScope } from './calculationScope';
import type {
  Calculation4,
  CalculationContentRead4,
  CalculationVersionRead4,
  ModelRevisionRead5,
  FrozenConfigurationRead7,
  StudyBriefVersionRead2,
} from './contract';
import { EstimatesPanel, SamplingDialog, refKey } from './CalculationDesign';
import { AnalysisResults, analysisPorts } from './AnalysisResults';
import { suggestCriterionOutput } from './criterionLabels';
import { modelPorts } from './ConfigurationPanel';
import {
  ActionDialog,
  Button,
  Checkbox,
  CollectionToolbar,
  CreateVersionAction,
  PageHeader,
  Panel,
  SectionHelp,
  ResourceCard,
  RecordState,
  RecordDetails,
  StatusTag,
  FormField,
  TextArea,
  TextInput,
  VersionSelect,
  SavedField,
} from './design';
import { resolvedUnit } from './unitLabels';

/** "1 configuration", "2 configurations". */
const count = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`;

type EditorBasis = {
  configurations: ConfigurationSummary1[];
  snapshot: ModelRevisionRead5 | null;
  brief: StudyBriefVersionRead2 | null;
};

/** Create a calculation or save its next version: a hand-picked set of this model version's
 * configurations and, for each criterion of the latest saved brief version, the output that
 * measures it. Revisions retain their saved bindings; new analyses keep unique name/unit matches. */
function CalculationEditor({
  api,
  study,
  scope,
  current,
  creation,
  onSaved,
}: {
  api: HyprnMvpApi;
  study: string;
  scope: CalculationScope;
  current?: CalculationVersionRead4;
  creation?: {
    activation: number;
    active: boolean;
    name: string;
    description: string;
    onBusy: (busy: boolean) => void;
    readOnly?: boolean;
  };
  onSaved: (version: CalculationVersionRead4) => void;
}) {
  const formId = useId();
  const [basis, setBasis] = useState<EditorBasis | null>(null);
  const [localName, setName] = useState(current?.content.name ?? '');
  const name = creation?.name ?? localName;
  const [localDescription, setDescription] = useState(current?.content.description ?? '');
  const description = creation?.description ?? localDescription;
  const [members, setMembers] = useState<string[]>(
    current?.content.configuration_revision_ids ?? [],
  );
  const [error, setError] = useState<unknown>(null);
  const [saving, setSaving] = useState(false);
  const [done, setDone] = useState(0);
  const read = useStudyRead(api, study);
  // The basis loads when the dialog opens, never while the list or record is only read.
  function open() {
    setError(null);
    void read(
      async (signal) => {
        const configurations = await scopeConfigurations(api, study, scope, signal);
        const first = configurations[0];
        const snapshot = first
          ? (await api.configuration(study, first.configuration_revision_id, signal)).model_snapshot
          : null;
        const brief = current
          ? current.content.brief_version_id
            ? await api.briefVersion(study, current.content.brief_version_id, signal)
            : null
          : (await api.brief(study, signal)).latest_version;
        return { configurations, snapshot, brief };
      },
      setBasis,
      setError,
    );
  }
  useEffect(() => {
    if (creation?.active && creation.activation) open();
  }, [creation?.activation, creation?.active]);
  const outputs = basis?.snapshot
    ? modelPorts(basis.snapshot).filter((p) => p.direction === 'output')
    : [];
  const criteria = basis?.brief?.content.criteria ?? [];
  const selectedBindings = Object.fromEntries(
    criteria.map((c) => [
      c.criterion_id,
      suggestCriterionOutput(
        c,
        outputs.map((p) => ({
          key: refKey(p.target),
          name: p.name,
          units: resolvedUnit(p.units),
        })),
      ),
    ]),
  );
  async function save() {
    if (creation?.readOnly || !basis || !scope.model || !scope.revision) return;
    setSaving(true);
    creation?.onBusy(true);
    setError(null);
    const keepDesign =
      current?.content.design.kind === 'sampled' &&
      members.join() === current.content.configuration_revision_ids.join();
    const content = {
      schema_version: '4',
      estimate_plan:
        keepDesign && current.content.schema_version === '4' ? current.content.estimate_plan : null,
      name,
      description,
      model_id: scope.model,
      model_revision_id: scope.revision,
      configuration_revision_ids: members,
      // A sampled design carries over only with exactly its points; any other set is hand-picked.
      design: keepDesign ? current.content.design : { kind: 'hand_picked' },
      brief_version_id: basis.brief?.brief_version_id ?? null,
      criterion_bindings:
        current?.content.criterion_bindings ??
        criteria.flatMap((c) => {
          const port = outputs.find((p) => refKey(p.target) === selectedBindings[c.criterion_id]);
          return port ? [{ criterion_id: c.criterion_id, output: port.target }] : [];
        }),
    } as CalculationContentRead4;
    try {
      const saved = current
        ? await api.saveCalculationVersion(study, current.calculation_id, {
            command_id: crypto.randomUUID(),
            expected_version_id: current.calculation_version_id,
            content,
          })
        : await api.createCalculation(study, { command_id: crypto.randomUUID(), content });
      setDone((value) => value + 1);
      onSaved(saved);
    } catch (e) {
      setError(e);
    } finally {
      setSaving(false);
      creation?.onBusy(false);
    }
  }
  const title = current ? 'Analysis settings' : 'New analysis';
  const form = (
    <form
      id={formId}
      className="hf-form-stack"
      onSubmit={(event) => {
        event.preventDefault();
        void save();
      }}
    >
      {!creation && (
        <>
          <label>
            Name
            <TextInput
              aria-label="Analysis name"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
          <FormField label="Description" optional>
            <TextArea
              aria-label="Analysis description"
              placeholder="Sampling design, accuracy targets and numerical checks."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </FormField>
        </>
      )}
      <fieldset className="hf-form-section">
        <legend>Configurations</legend>
        {!basis && !error && <p role="status">Loading configurations…</p>}
        {basis && !basis.configurations.length && (
          <p>No saved configurations for this model version.</p>
        )}
        {creation && !!basis?.configurations.length && (
          <p className="context-line" role="status">
            {members.length === 0
              ? 'Select one or more configurations.'
              : count(members.length, 'configuration') + ' selected'}
          </p>
        )}
        <div className="hf-checklist" role="group" aria-label="Saved configurations">
          {basis?.configurations.map((c) => (
            <label key={c.configuration_revision_id} className="calculation-member">
              <Checkbox
                checked={members.includes(c.configuration_revision_id)}
                onChange={(e) =>
                  setMembers((previous) =>
                    e.target.checked
                      ? [...previous, c.configuration_revision_id]
                      : previous.filter((id) => id !== c.configuration_revision_id),
                  )
                }
              />
              {c.name}{basis.configurations.filter(item => item.name === c.name).length > 1
                && <span className="context-line"> · {c.configuration_revision_id.slice(0, 8)}</span>}
            </label>
          ))}
        </div>
      </fieldset>
      {error != null && <p role="alert">{message(error)}</p>}
      {!creation?.readOnly && (
        <DialogActions
          active={!creation || creation.active}
          primary={
            <Button
              type="submit"
              form={formId}
              variant="primary"
              disabled={!basis || saving || !name.trim() || members.length === 0}
            >
              {current ? 'Save version' : 'Save analysis'}
            </Button>
          }
        />
      )}
    </form>
  );
  if (creation) return form;
  return (
    <ActionDialog
      title={title}
      label={title}
      disabled={!scope.revision}
      completionKey={done}
      closeLabel="Cancel"
      onOpen={open}
    >
      {form}
    </ActionDialog>
  );
}

function AnalysisDialog({
  api,
  study,
  scope,
  current,
  canRevise = true,
  onSaved,
}: {
  api: HyprnMvpApi;
  study: string;
  scope: CalculationScope;
  current?: CalculationVersionRead4;
  canRevise?: boolean;
  onSaved: (versionId: string) => void;
}) {
  const [activation, setActivation] = useState(0);
  const [done, setDone] = useState(0);
  const [source, setSource] = useState(
    current?.content.design.kind === 'sampled' ? 'sample' : 'existing',
  );
  const [name, setName] = useState(current?.content.name ?? '');
  const [description, setDescription] = useState(current?.content.description ?? '');
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(!current);
  const [reset, setReset] = useState(0);
  const readOnly = !!current && !editing;
  const sampling = source === 'sample';
  const saved = (id: string) => {
    setDone((n) => n + 1);
    onSaved(id);
  };
  return (
    <ActionDialog
      purpose={readOnly ? 'reader' : 'action'}
      title={current ? 'Analysis settings' : 'New analysis'}
      help="analysisSettings"
      disabled={!scope.revision}
      completionKey={done}
      closeLabel={readOnly ? 'Done' : 'Cancel'}
      onOpen={() => {
        if (current && !busy) {
          setEditing(false);
          setName(current.content.name);
          setDescription(current.content.description);
          setSource(current.content.design.kind === 'sampled' ? 'sample' : 'existing');
          setReset((n) => n + 1);
        }
        setActivation((n) => n + 1);
      }}
    >
      <CollectionToolbar
        summary={
          current ? (
            readOnly ? (
              <RecordState state="saved" />
            ) : (
              <StatusTag tone="advisory">New version · unsaved</StatusTag>
            )
          ) : null
        }
        actions={
          <>
            {readOnly && canRevise && (
              <CreateVersionAction
                disabled={busy || !!api.pending}
                onClick={() => setEditing(true)}
              />
            )}
          </>
        }
      />
      <fieldset
        className={readOnly ? 'hf-form-section hf-form-readonly' : 'hf-form-section'}
        disabled={readOnly}
        aria-label="Analysis settings fields"
      >
        {readOnly ? (
          <>
            <SavedField label="Name">{name}</SavedField>
            {description && <SavedField label="Description">{description}</SavedField>}
          </>
        ) : (
          <>
            <label className="hf-form-field">
              Name
              <TextInput
                aria-label="Analysis name"
                value={name}
                disabled={busy}
                onChange={(e) => setName(e.target.value)}
              />
            </label>
            <FormField label="Description" optional>
              <TextArea
                aria-label="Analysis description"
                placeholder="Sampling design, accuracy targets and numerical checks."
                value={description}
                disabled={busy}
                onChange={(e) => setDescription(e.target.value)}
              />
            </FormField>
          </>
        )}
        <fieldset className="hf-form-section" disabled={busy}>
          <legend>Configurations</legend>
          <div className="hf-choice-grid">
            <Button
              className="hf-choice-card"
              aria-label="Select configurations"
              aria-pressed={!sampling}
              onClick={() => setSource('existing')}
            >
              <strong>Select configurations</strong>
              <span>Choose one or more saved configurations.</span>
            </Button>
            <Button
              className="hf-choice-card"
              aria-label="Generate samples"
              aria-pressed={sampling}
              onClick={() => setSource('sample')}
            >
              <strong>Generate samples</strong>
              <span>Create configurations across input ranges.</span>
            </Button>
          </div>
        </fieldset>
        {activation > 0 && (
          <>
            <div hidden={sampling}>
              <CalculationEditor
                key={reset}
                api={api}
                study={study}
                scope={scope}
                current={current}
                creation={{
                  activation,
                  active: !sampling,
                  name,
                  description,
                  onBusy: setBusy,
                  readOnly,
                }}
                onSaved={(v) => saved(v.calculation_version_id)}
              />
            </div>
            <div hidden={!sampling}>
              <SamplingDialog
                key={reset}
                api={api}
                study={study}
                scope={scope}
                current={current}
                creation={{
                  activation,
                  active: sampling,
                  name,
                  description,
                  onBusy: setBusy,
                  readOnly,
                }}
                onSaved={saved}
              />
            </div>
          </>
        )}
      </fieldset>
    </ActionDialog>
  );
}

export function CalculationList({
  api,
  study,
  scope,
  onOpen,
}: {
  api: HyprnMvpApi;
  study: string;
  scope: CalculationScope;
  onOpen: (versionId: string) => void;
}) {
  const collection = useCollectionRead<Calculation4, number>({
    api,
    study,
    scope: JSON.stringify([scope.model, scope.revision]),
    load: async (cursor, signal) => {
      const page = await api.calculations(study, scope.revision!, cursor, signal);
      return { rows: page.items, next: page.next_cursor };
    },
    identity: (row) => row.calculation_id,
  });
  const shown = collection.rows;
  return (
    <Panel label="Analyses" bodyClassName="hf-flow">
      <CollectionStatus
        entity={{ singular: 'analysis', plural: 'analyses' }}
        state={collection.state}
        onMore={() => void collection.more()}
        onRetry={() => void collection.retry()}
        actions={<AnalysisDialog api={api} study={study} scope={scope} onSaved={onOpen} />}
      />
      {shown.map((c) => {
        const content = c.latest_version.content;
        return (
          <ResourceCard
            key={c.calculation_id}
            level={3}
            title={content.name}
            facts={[
              `Version ${c.latest_version.version_number}`,
              count(content.configuration_revision_ids.length, 'configuration'),
            ]}
            actions={
              <OpenLink onClick={() => onOpen(c.latest_version.calculation_version_id)}>
                Open analysis
              </OpenLink>
            }
          />
        );
      })}
    </Panel>
  );
}

type RecordBasis = {
  version: CalculationVersionRead4;
  brief: StudyBriefVersionRead2 | null;
  names: Record<string, string>;
  snapshot: ModelRevisionRead5 | null;
  frozen: FrozenConfigurationRead7;
};

/** One exact calculation version: its configurations, criterion bindings and runs, each run
 * evaluated against the pinned brief version's criteria. */
export function CalculationRecord({
  api,
  study,
  scope,
  versionId,
  onOpen,
  onList,
  onOpenConfiguration,
  onOpenRun,
}: {
  api: HyprnMvpApi;
  study: string;
  scope: CalculationScope;
  versionId: string;
  onOpen: (versionId: string) => void;
  onList: () => void;
  onOpenConfiguration: (configurationRevisionId: string) => void;
  onOpenRun: (runId: string) => void;
}) {
  const [basis, setBasis] = useState<RecordBasis | null>(null);
  const [error, setError] = useState<unknown>(null);
  const read = useStudyRead(api, study);
  const [resultsRevision, setResultsRevision] = useState(0);
  const [executionPins, setExecutionPins] = useState<Record<string, string | null> | null>(null);
  const versionCollection = useCollectionRead<CalculationVersionRead4, number>({
    api,
    study,
    scope: basis?.version.calculation_id ?? versionId,
    enabled: !!basis,
    load: async (cursor, signal) => {
      const page = await api.calculationVersions(
        study,
        basis!.version.calculation_id,
        cursor,
        signal,
      );
      return { rows: page.items, next: page.next_cursor };
    },
    identity: (row) => row.calculation_version_id,
    onUnavailable: () => {
      setBasis(null);
      setError(new Error('Access to this analysis is no longer available.'));
    },
  });
  useEffect(() => {
    setBasis(null);
    setExecutionPins(null);
    setError(null);
    void read(
      async (signal) => {
        const version = await api.calculationVersion(study, versionId, signal);
        const content = version.content;
        const [brief, configurations, frozen] = await Promise.all([
          content.brief_version_id
            ? api.briefVersion(study, content.brief_version_id, signal)
            : Promise.resolve(null),
          scopeConfigurations(
            api,
            study,
            { model: content.model_id, revision: content.model_revision_id },
            signal,
          ),
          api.configuration(study, content.configuration_revision_ids[0], signal),
        ]);
        return {
          version,
          brief,
          names: Object.fromEntries(
            configurations.map((c) => [c.configuration_revision_id, c.name]),
          ),
          snapshot: frozen.model_snapshot,
          frozen,
        };
      },
      setBasis,
      setError,
    );
  }, [study, versionId]);
  if (error != null)
    return (
      <Panel label="Analysis">
        <p role="alert">{message(error)}</p>
        <ReturnLink onClick={onList} label="Return to all analyses" />
      </Panel>
    );
  if (!basis) return <p role="status">Loading analysis…</p>;
  const { version, brief, names, snapshot, frozen } = basis;
  const shownVersions = [
    ...new Set([
      ...versionCollection.rows.map((v) => v.calculation_version_id),
      version.calculation_version_id,
    ]),
  ];
  const content = version.content;
  const criteria = brief?.content.criteria ?? [];
  const outputs = analysisPorts(snapshot)
    .filter((p) => p.direction === 'output')
    .map((p) => ({ target: p.target, label: p.label, units: resolvedUnit(p.units) ?? '' }));
  return (
    <div className="calculation-record">
      <PageHeader
        level={2}
        title={content.name}
        returnTo={{ label: 'Return to all analyses', onClick: onList }}
        details={
          <>
            <RecordDetails kind="Analysis" metadata={<RecordState state="saved" />}>
              <pre tabIndex={0} aria-label="Analysis record JSON">
                {JSON.stringify(version, null, 2)}
              </pre>
            </RecordDetails>
          </>
        }
        controls={
          <div className="hf-flow">
            <VersionSelect
              label="Analysis version"
              value={version.calculation_version_id}
              versions={shownVersions.map((id) => ({
                id,
                number: (id === version.calculation_version_id
                  ? version
                  : versionCollection.rows.find((v) => v.calculation_version_id === id)
                )?.version_number,
              }))}
              onChange={onOpen}
            />
            {(versionCollection.state.status !== 'ready' ||
              versionCollection.state.more ||
              versionCollection.state.error) && (
              <CollectionStatus
                entity={{ singular: 'analysis version', plural: 'analysis versions' }}
                state={
                  versionCollection.state.status === 'ready'
                    ? { ...versionCollection.state, count: shownVersions.length }
                    : versionCollection.state
                }
                onMore={() => void versionCollection.more()}
                onRetry={() => void versionCollection.retry()}
              />
            )}
          </div>
        }
        actions={
          scope.revision === content.model_revision_id ? (
            <AnalysisDialog
              key={version.calculation_version_id}
              api={api}
              study={study}
              scope={scope}
              current={version}
              canRevise={
                version.calculation_version_id === versionCollection.rows[0]?.calculation_version_id
              }
              onSaved={onOpen}
            />
          ) : undefined
        }
      />
      {content.description && (
        <Panel label="Analysis description" title="Description" headingLevel={3}>
          <p className="hf-saved-value">{content.description}</p>
        </Panel>
      )}
      <Panel
        label="Results"
        title="Results"
        help={<SectionHelp topic="analysisResults" />}
        headingLevel={3}
        bodyClassName="hf-flow"
      >
        <AnalysisExecutionPanel
          key={versionId}
          api={api}
          study={study}
          version={version}
          onProgress={(execution) => {
            setExecutionPins(
              execution
                ? Object.fromEntries(
                    execution.runs.map((r) => [r.configuration_revision_id, r.run_id]),
                  )
                : null,
            );
            setResultsRevision((value) => value + 1);
          }}
        />
        <AnalysisResults
          key={versionId}
          api={api}
          study={study}
          version={version}
          criteria={criteria}
          names={names}
          snapshot={snapshot}
          frozen={frozen}
          refresh={resultsRevision}
          pinnedRuns={executionPins}
          onOpenConfiguration={onOpenConfiguration}
          onOpenRun={onOpenRun}
        />
      </Panel>
      <EstimatesPanel
        api={api}
        study={study}
        version={version}
        outputs={outputs}
        refresh={resultsRevision}
      />
    </div>
  );
}
