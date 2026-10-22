import type { HyprnMvpApi } from './api';
import { emptyBrief } from './BriefController';

/** Retain command identities across interrupted setup; never create a replacement study. */
export function studyStart(name: string, question: string, autonomous: boolean) {
  return {
    name,
    question,
    autonomous,
    createCommand: crypto.randomUUID(),
    briefCommand: crypto.randomUUID(),
    messageCommand: crypto.randomUUID(),
    studyId: null as string | null,
    briefSaved: false,
  };
}
export type StudyStart = ReturnType<typeof studyStart>;

export async function completeStudyStart(api: HyprnMvpApi, start: StudyStart) {
  if (!start.studyId)
    start.studyId = (await api.createStudy(start.name, start.createCommand)).study_id;
  if (!start.briefSaved) {
    await api.saveBriefDraft(start.studyId, {
      command_id: start.briefCommand,
      expected_revision: null,
      content: {
        ...emptyBrief(),
        question: start.question,
        original_question: { text: start.question, attribution: { kind: 'human', label: null } },
      },
    });
    start.briefSaved = true;
  }
  if (start.autonomous) {
    await api.assistantSend(start.studyId, {
      command_id: start.messageCommand,
      text:
        `Complete this study autonomously from the question saved in its brief:\n\n${start.question}\n\n` +
        'Use the engineering playbook to complete the brief, execute the analyses and save a ' +
        'verified answer with interactive exploration. Ask if missing information prevents a ' +
        'defensible answer; report any remaining gap without weakening accuracy checks.',
    });
  }
  return start.studyId;
}
