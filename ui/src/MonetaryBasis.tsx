import { useState } from 'react';
import type { EvidenceRecord, HyprnMvpApi } from './api';
import type { ModelExplanationContent3, MonetaryQuantityBasis1, UnitCatalog2 } from './contract';
import type { Snapshot } from './GraphView';
import { quantityDefinitions } from './quantityDefinitions';
import { resolvedUnit } from './unitLabels';
import { EvidenceList } from './EvidenceView';
import { EvidencePicker } from './EvidencePicker';
import {
  Button,
  FieldHint,
  FormField,
  ReadingSection,
  ReadingStack,
  TextArea,
  TextInput,
} from './design';

type Props = {
  snapshot: Snapshot;
  items: ModelExplanationContent3['monetary_quantities'];
  evidence: EvidenceRecord[];
};

export function MonetaryBasisReader({ snapshot, items, evidence }: Props) {
  const ports = quantityDefinitions(snapshot);
  return (
    <ReadingStack>
      {items.map((item) => {
        const port = ports.find(
          (p) => p.instance.instance_id === item.instance_id && p.port.port_id === item.port_id,
        );
        return (
          <ReadingSection key={item.instance_id + '/' + item.port_id} aria-label="Price basis">
            <h4>
              {port?.port.name ?? 'Quantity'} · {item.catalogue_expression}
            </h4>
            <p>{item.price_year} prices</p>
            <p className="context-copy">{item.economic_basis}</p>
            <EvidenceList
              records={evidence}
              ids={item.evidence_links.map((l) => l.evidence_version_id)}
              links={item.evidence_links}
            />
          </ReadingSection>
        );
      })}
    </ReadingStack>
  );
}

export function MonetaryBasisEditor({
  snapshot,
  items,
  evidence,
  catalog,
  api,
  studyId,
  onChange,
  onEvidence,
}: Props & {
  catalog: UnitCatalog2 | null;
  api: HyprnMvpApi;
  studyId: string;
  onChange: (items: MonetaryQuantityBasis1[]) => void;
  onEvidence: (items: EvidenceRecord[]) => void;
}) {
  const [picking, setPicking] = useState<string | null>(null);
  const quantities = quantityDefinitions(snapshot).flatMap((p) => {
    const unit = catalog?.monetary_units.find((u) => u.expression === resolvedUnit(p.port.units));
    return unit
      ? [{ ...p, expression: unit.expression, key: p.instance.instance_id + '/' + p.port.port_id }]
      : [];
  });
  if (!quantities.length) return null;
  return (
    <ReadingStack>
      <h4>Price basis</h4>
      {quantities.map((p) => {
        const savedItem = items.find(
          (i) => i.instance_id === p.instance.instance_id && i.port_id === p.port.port_id,
        );
        const changedUnit = savedItem && savedItem.catalogue_expression !== p.expression;
        const item = changedUnit ? undefined : savedItem;
        const update = (fields: Partial<MonetaryQuantityBasis1>) =>
          onChange([
            ...items.filter(
              (i) => i.instance_id !== p.instance.instance_id || i.port_id !== p.port.port_id,
            ),
            {
              price_year: 0,
              economic_basis: '',
              evidence_links: [],
              ...item,
              ...fields,
              instance_id: p.instance.instance_id,
              port_id: p.port.port_id,
              catalogue_expression: p.expression,
            },
          ]);
        return (
          <ReadingSection key={p.key} aria-label={'Price basis · ' + p.port.name}>
            <h5>
              {p.port.name} · {p.expression}
            </h5>
            {changedUnit && (
              <FieldHint>The unit changed. Enter the price basis for {p.expression}.</FieldHint>
            )}
            <FormField label="Price year">
              <TextInput
                type="number"
                min={1800}
                max={9999}
                step={1}
                aria-label={'Price year · ' + p.port.name}
                value={item?.price_year || ''}
                onChange={(e) => update({ price_year: Number(e.target.value) })}
              />
            </FormField>
            <FormField label="Cost basis">
              <TextArea
                aria-label={'Cost basis · ' + p.port.name}
                value={item?.economic_basis ?? ''}
                maxLength={4096}
                onChange={(e) => update({ economic_basis: e.target.value })}
              />
            </FormField>
            <EvidenceList
              records={evidence}
              ids={(item?.evidence_links ?? []).map((l) => l.evidence_version_id)}
              links={item?.evidence_links ?? []}
            />
            <Button onClick={() => setPicking(p.key)}>Add price evidence</Button>
            {picking === p.key && (
              <EvidencePicker
                api={api}
                studyId={studyId}
                ownerKey={'price-basis/' + p.key}
                label={'Price basis · ' + p.port.name}
                scope={null}
                assumption
                onRecords={onEvidence}
                onClose={() => setPicking(null)}
                onAttach={(record, relation) => {
                  if (!relation) return;
                  onEvidence([
                    ...evidence.filter((e) => e.evidence_id !== record.evidence_id),
                    record,
                  ]);
                  const links = item?.evidence_links ?? [];
                  if (
                    !links.some(
                      (l) =>
                        l.evidence_version_id === record.evidence_version_id &&
                        l.relation === relation,
                    )
                  )
                    update({
                      evidence_links: [
                        ...links,
                        { evidence_version_id: record.evidence_version_id, relation },
                      ],
                    });
                  setPicking(null);
                }}
              />
            )}
          </ReadingSection>
        );
      })}
    </ReadingStack>
  );
}
