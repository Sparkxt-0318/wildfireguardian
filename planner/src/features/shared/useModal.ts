/**
 * Modal behaviour shared by the feature dialogs: Esc closes, Tab/Shift+Tab stay inside the dialog
 * (focus trap), focus moves into the dialog on open and returns to the opener on close, and the
 * page behind does not scroll.
 */
import { useEffect, useRef, type RefObject } from 'react';

const FOCUSABLE =
  'a[href], area[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), ' +
  'textarea:not([disabled]), iframe, [tabindex]:not([tabindex="-1"]), [contenteditable="true"]';

export function focusableIn(root: HTMLElement): HTMLElement[] {
  return Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE)).filter((el) => {
    if (el.closest('[inert], [hidden], [aria-hidden="true"]')) return false;
    // checkVisibility (Chromium 105+, Safari 17.4+) skips display:none / content-visibility; jsdom lacks it.
    const cv = (el as HTMLElement & { checkVisibility?: () => boolean }).checkVisibility;
    return typeof cv === 'function' ? cv.call(el) : true;
  });
}

export function useModal(ref: RefObject<HTMLElement | null>, open: boolean, onClose: () => void, opts: { initialFocus?: string } = {}) {
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  const initial = opts.initialFocus;

  useEffect(() => {
    if (!open) return undefined;
    const opener = (typeof document !== 'undefined' ? document.activeElement : null) as HTMLElement | null;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const focusFirst = () => {
      const r = ref.current;
      if (!r) return;
      // ':self' focuses the dialog container (no focus ring on a button at open; Tab enters the dialog)
      const target = initial === ':self' ? r : ((initial ? r.querySelector<HTMLElement>(initial) : null) ?? focusableIn(r)[0] ?? r);
      target.focus({ preventScroll: true });
    };
    const raf = typeof requestAnimationFrame === 'function' ? requestAnimationFrame(focusFirst) : null;
    if (raf === null) focusFirst();

    const onKey = (e: KeyboardEvent) => {
      const r = ref.current;
      if (!r) return;
      if (e.key === 'Escape') {
        e.stopPropagation();
        e.preventDefault();
        closeRef.current();
        return;
      }
      if (e.key !== 'Tab') return;
      const items = focusableIn(r);
      if (items.length === 0) {
        e.preventDefault();
        r.focus();
        return;
      }
      const first = items[0]!;
      const last = items[items.length - 1]!;
      const active = document.activeElement as HTMLElement | null;
      const inside = active ? r.contains(active) : false;
      if (e.shiftKey && (active === first || !inside)) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && (active === last || !inside)) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', onKey, true);
    return () => {
      document.removeEventListener('keydown', onKey, true);
      if (raf !== null && typeof cancelAnimationFrame === 'function') cancelAnimationFrame(raf);
      document.body.style.overflow = prevOverflow;
      if (opener && typeof opener.focus === 'function' && document.contains(opener)) opener.focus({ preventScroll: true });
    };
  }, [open, ref, initial]);
}
