import type { ReactNode } from "react";
import type { DangerLevel } from "../api/client";

/**
 * THE one giant primary button (spec §1.3): one per screen, colored by the
 * current danger level, huge tap target.
 */
export function BigButton({
  level,
  onClick,
  children,
  sub,
}: {
  level: DangerLevel;
  onClick: () => void;
  children: ReactNode;
  /** Secondary-language line under the main label. */
  sub?: string;
}) {
  return (
    <button
      type="button"
      className={`btn-giant level-${level}`}
      onClick={onClick}
    >
      <span>
        {children}
        {sub ? <span className="btn-sub">{sub}</span> : null}
      </span>
    </button>
  );
}
