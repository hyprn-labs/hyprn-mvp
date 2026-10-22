/** Explicit authored-note format; never infer quotation boundaries from legacy prose. */
export const evidenceContentPrefix = 'HYPRN evidence/1\n';
export type EvidenceContent = {
  excerpt: string;
  source_reference: string;
  location: string;
  explanation: string;
};
export function readEvidenceContent(content: string): EvidenceContent | null {
  if (!content.startsWith(evidenceContentPrefix)) return null;
  try {
    const value = JSON.parse(content.slice(evidenceContentPrefix.length));
    const fields = ['excerpt', 'source_reference', 'location', 'explanation'];
    if (!value || typeof value !== 'object' || Array.isArray(value) ||
        Object.keys(value).length !== fields.length ||
        fields.some(key => typeof value[key] !== 'string' || !value[key].trim() || value[key].length > 4096)) return null;
    return value as EvidenceContent;
  } catch { return null; }
}
export function writeEvidenceContent(value: EvidenceContent): string {
  return evidenceContentPrefix + JSON.stringify(value);
}
export function evidenceSummary(content: string): string {
  return readEvidenceContent(content)?.explanation ?? content;
}
