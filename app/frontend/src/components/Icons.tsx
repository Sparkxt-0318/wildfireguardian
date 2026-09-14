// Hand-drawn inline SVG glyphs. Stroke-based, bold, legible at small sizes.
// currentColor everywhere so icons inherit text color.

import type { CardIcon } from "../api/client";
import type { DangerLevel } from "../api/client";

interface IconProps {
  size?: number;
}

const base = (size: number) =>
  ({
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 2.2,
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": true,
  }) as const;

export function IconHome({ size = 24 }: IconProps) {
  return (
    <svg {...base(size)}>
      <path d="M3 11 L12 3 L21 11" />
      <path d="M5 10 V21 H19 V10" />
      <path d="M10 21 V14 H14 V21" />
    </svg>
  );
}

export function IconMap({ size = 24 }: IconProps) {
  return (
    <svg {...base(size)}>
      <path d="M9 4 L3 6 V20 L9 18 L15 20 L21 18 V4 L15 6 L9 4 Z" />
      <path d="M9 4 V18" />
      <path d="M15 6 V20" />
    </svg>
  );
}

export function IconGuide({ size = 24 }: IconProps) {
  return (
    <svg {...base(size)}>
      <path d="M4 4 H14 A4 4 0 0 1 18 8 V20 H8 A4 4 0 0 0 4 24 Z" transform="translate(1 -2)" />
      <path d="M9 8 H14" />
      <path d="M9 12 H14" />
    </svg>
  );
}

export function IconFamily({ size = 24 }: IconProps) {
  return (
    <svg {...base(size)}>
      <circle cx="8" cy="8" r="3.2" />
      <path d="M2.5 20 C2.5 15.5 5 13.5 8 13.5 C11 13.5 13.5 15.5 13.5 20" />
      <circle cx="17" cy="9.5" r="2.6" />
      <path d="M14 20 C14.5 16.5 15.5 15 17.5 15 C19.8 15 21.5 17 21.5 20" />
    </svg>
  );
}

export function IconSettings({ size = 24 }: IconProps) {
  return (
    <svg {...base(size)}>
      <circle cx="12" cy="12" r="3.4" />
      <path d="M12 2.5 V5.5 M12 18.5 V21.5 M2.5 12 H5.5 M18.5 12 H21.5 M5.2 5.2 L7.3 7.3 M16.7 16.7 L18.8 18.8 M18.8 5.2 L16.7 7.3 M7.3 16.7 L5.2 18.8" />
    </svg>
  );
}

export function IconSpeaker({ size = 28 }: IconProps) {
  return (
    <svg {...base(size)}>
      <path d="M4 9 H8 L13 4.5 V19.5 L8 15 H4 Z" fill="currentColor" stroke="none" />
      <path d="M16 8.5 C17.3 9.6 17.3 14.4 16 15.5" />
      <path d="M18.7 6 C21 8.2 21 15.8 18.7 18" />
    </svg>
  );
}

export function IconStop({ size = 28 }: IconProps) {
  return (
    <svg {...base(size)}>
      <rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function IconPhone({ size = 24 }: IconProps) {
  return (
    <svg {...base(size)}>
      <path d="M5 3 H9 L10.8 8 L8.5 9.8 C9.6 12.2 11.8 14.4 14.2 15.5 L16 13.2 L21 15 V19 C21 20.1 20.1 21 19 21 C10.2 20.4 3.6 13.8 3 5 C3 3.9 3.9 3 5 3 Z" />
    </svg>
  );
}

export function IconFlame({ size = 24 }: IconProps) {
  return (
    <svg {...base(size)}>
      <path d="M12 3 C14 7 18 8.5 18 13.5 C18 17.6 15.3 20.5 12 20.5 C8.7 20.5 6 17.6 6 13.5 C6 10.5 7.5 9 8.8 7.4 C9.2 9.8 10.2 10.7 11 11.1 C10.4 8 11 5.6 12 3 Z" />
    </svg>
  );
}

export function IconWind({ size = 24 }: IconProps) {
  return (
    <svg {...base(size)}>
      <path d="M3 8 H13 A2.6 2.6 0 1 0 10.4 5.2" />
      <path d="M3 13 H18 A2.8 2.8 0 1 1 15.2 15.9" />
      <path d="M3 18 H10" />
    </svg>
  );
}

export function IconRoute({ size = 24 }: IconProps) {
  return (
    <svg {...base(size)}>
      <circle cx="6" cy="19" r="2.4" />
      <circle cx="18" cy="5" r="2.4" />
      <path d="M6 16.5 V12 A3 3 0 0 1 9 9 H15 A3 3 0 0 0 18 6.8" />
    </svg>
  );
}

export function IconShelter({ size = 24 }: IconProps) {
  return (
    <svg {...base(size)}>
      <path d="M3 11 L12 3.5 L21 11" />
      <path d="M5.5 9.8 V20.5 H18.5 V9.8" />
      <path d="M12 20.5 V14.5" />
    </svg>
  );
}

export function IconClock({ size = 24 }: IconProps) {
  return (
    <svg {...base(size)}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 6.5 V12 L15.8 14.2" />
    </svg>
  );
}

export function IconCheck({ size = 24 }: IconProps) {
  return (
    <svg {...base(size)}>
      <path d="M4 12.5 L9.5 18 L20 6.5" strokeWidth={3} />
    </svg>
  );
}

export function IconWarnTriangle({ size = 24 }: IconProps) {
  return (
    <svg {...base(size)}>
      <path d="M12 3.5 L22 20.5 H2 Z" />
      <path d="M12 9.5 V14.5" strokeWidth={2.6} />
      <path d="M12 17.6 V17.8" strokeWidth={3.2} />
    </svg>
  );
}

export function IconRun({ size = 24 }: IconProps) {
  return (
    <svg {...base(size)}>
      <circle cx="14.5" cy="4.5" r="2.1" fill="currentColor" stroke="none" />
      <path d="M9 9.5 L13 7.5 L16 10 L19 11" />
      <path d="M13 7.5 L12 13 L15 16 L14.5 21" />
      <path d="M12 13 L8.5 15.5 L6 20" />
    </svg>
  );
}

export function IconLocation({ size = 24 }: IconProps) {
  return (
    <svg {...base(size)}>
      <circle cx="12" cy="12" r="3" fill="currentColor" stroke="none" />
      <circle cx="12" cy="12" r="7.5" />
      <path d="M12 1.8 V4.6 M12 19.4 V22.2 M1.8 12 H4.6 M19.4 12 H22.2" />
    </svg>
  );
}

/** Card icon by the API's icon name (contract §5.1). */
export function CardIconGlyph({
  icon,
  size = 40,
}: {
  icon: CardIcon;
  size?: number;
}) {
  switch (icon) {
    case "flame":
      return <IconFlame size={size} />;
    case "wind":
      return <IconWind size={size} />;
    case "route":
      return <IconRoute size={size} />;
    case "phone":
      return <IconPhone size={size} />;
    case "shelter":
      return <IconShelter size={size} />;
    case "clock":
      return <IconClock size={size} />;
    case "check":
      return <IconCheck size={size} />;
    case "home":
      return <IconHome size={size} />;
  }
}

/** Danger-level icon (color+icon+word rule — never color alone). */
export function DangerIconGlyph({
  level,
  size = 40,
}: {
  level: DangerLevel;
  size?: number;
}) {
  switch (level) {
    case "SAFE":
      return <IconCheck size={size} />;
    case "WATCH":
      return <IconWarnTriangle size={size} />;
    case "GO":
      return <IconRun size={size} />;
  }
}
