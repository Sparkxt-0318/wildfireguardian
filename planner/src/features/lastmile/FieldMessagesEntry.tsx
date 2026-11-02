/**
 * Right-panel entry of the last-mile kit: a short section with one button that opens the
 * "현장 전달 문구 / Field messages" dialog for the selected origin. It builds the messages of every
 * origin of the recorded scenario on screen (only while the dialog is open) and loads the deadline
 * explanations, if the static file exists, from the app's own origin. In drawn-zone mode (an
 * assumption) and without results it explains why nothing is offered.
 *
 *   <FieldMessagesEntry originId={place.id} />
 */
import { useEffect, useMemo, useState } from 'react';
import { useLang } from '../../i18n';
import { pick } from '../shared/strings';
import { useIsResearchOrigin, useLastMileAvailability, useLastMileInputs } from './connect';
import { loadExplanation, type ExplanationState } from './explanation';
import { FieldMessagesDialog } from './FieldMessagesDialog';
import { buildFieldMessages } from './messages';
import { UI } from './strings';

export function FieldMessagesEntry({ originId }: { originId: string }) {
  const lang = useLang();
  const t = (s: { ko: string; en: string }) => pick(s, lang);
  const avail = useLastMileAvailability();
  const research = useIsResearchOrigin(originId);
  const [open, setOpen] = useState(false);
  const { inputs, args } = useLastMileInputs(open);
  const [explanation, setExplanation] = useState<ExplanationState>({ state: 'loading' });
  const regionId = args?.region.id ?? null;
  const inputTime = args?.scenario.inputTimeIso ?? null;
  const setId = args?.scenario.scenarioSetId ?? null;

  useEffect(() => {
    if (!open || !regionId || !inputTime || !setId) return undefined;
    let alive = true;
    setExplanation({ state: 'loading' });
    void loadExplanation({ regionId, inputTimeIso: inputTime, scenarioSetId: setId }).then((s) => {
      if (alive) setExplanation(s);
    });
    return () => {
      alive = false;
    };
  }, [open, regionId, inputTime, setId]);

  const file = explanation.state === 'ready' ? explanation.file : null;
  const items = useMemo(() => inputs.map((i) => buildFieldMessages(i, file)), [inputs, file]);
  const note = !avail.ok ? (avail.reason === 'drawn' ? t(UI.drawnDisabled) : t(UI.noData)) : research ? t(UI.researchNote) : t(UI.sectionNote);

  return (
    <div className="section" data-testid="field-messages-entry">
      <div className="section-title">{t(UI.sectionTitle)}</div>
      <button type="button" className="btn btn-block" disabled={!avail.ok} onClick={() => setOpen(true)} data-testid="field-messages-open">
        {t(UI.open)}
      </button>
      <span className="small-note">{note}</span>
      {open ? (
        <FieldMessagesDialog open={open} onClose={() => setOpen(false)} lang={lang} items={items} initialOriginId={originId} explanation={explanation} />
      ) : null}
    </div>
  );
}

export default FieldMessagesEntry;
