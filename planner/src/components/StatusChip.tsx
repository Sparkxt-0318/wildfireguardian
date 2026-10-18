import type { Verdict } from '../domain/types';
import { useT } from '../i18n';
import { UnresolvedIcon, VerdictIcon, WindowIcon } from './Icons';

const ICON_COLOR: Record<Verdict, string> = {
  checked_route: '#14824A',
  model_no_route: '#FFFFFF',
  unresolved: '#3A3A3E',
};

/** Status = colour + icon + text (never colour alone). */
export function StatusChip({ verdict, label }: { verdict: Verdict | 'window'; label?: string }) {
  const t = useT();
  if (verdict === 'window') {
    return (
      <span className="status window">
        <WindowIcon size={12} />
        {label ?? t('verdict.window')}
      </span>
    );
  }
  return (
    <span className={`status ${verdict}`}>
      <VerdictIcon verdict={verdict} size={12} color={ICON_COLOR[verdict]} />
      {label ?? t(`verdict.${verdict}`)}
    </span>
  );
}

/** "시험 데이터 · 평가 호스트 아님" — results computed on a non-evaluation host (neutral grey, never green). */
export function TestDataChip({ short = false }: { short?: boolean }) {
  const t = useT();
  return (
    <span className="test-chip" title={t('data.testDataTip')} data-testid={short ? 'test-badge' : 'test-data'}>
      <UnresolvedIcon size={11} color="#3A3A3E" />
      {short ? t('test.badge') : t('data.testData')}
    </span>
  );
}
