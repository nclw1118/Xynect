/** Parse any dimension string to total inches. Returns null if unparseable. */
export function parseToInches(s: string | null | undefined): number | null {
  if (!s) return null;
  const v = s.trim().toLowerCase();
  // feet-inches compound: 3'-6", 3' 6", 3 ft 6 in, 3'6"
  const compound = v.match(/^([\d.]+)\s*(?:ft|feet|')[\s'-]*([\d.]+)/);
  if (compound) return parseFloat(compound[1]) * 12 + parseFloat(compound[2]);
  // feet only: 3 ft, 3.5', 3'
  const ft = v.match(/^([\d.]+)\s*(?:ft|feet|')\s*$/);
  if (ft) return parseFloat(ft[1]) * 12;
  // bare number or inches: 42, 42 in, 42"
  const num = v.match(/^([\d.]+)/);
  if (num) return parseFloat(num[1]);
  return null;
}

/** Split total inches into floor feet and remaining inches. */
export function inchesToParts(totalInches: number): { ft: number; inches: number } {
  const rounded = parseFloat(totalInches.toFixed(4));
  const ft = Math.floor(rounded / 12);
  const inches = parseFloat((rounded - ft * 12).toFixed(4));
  return { ft, inches };
}

/** Parse a dimension string to {ft, inches} parts. Returns null if unparseable. */
export function parseDimParts(
  s: string | null | undefined
): { ft: number; inches: number } | null {
  const total = parseToInches(s);
  if (total === null) return null;
  return inchesToParts(total);
}

/** Format feet + inches as architectural notation: 3'-6" */
export function formatArch(ft: number, inches: number): string {
  return `${ft}'-${inches}"`;
}

/** Build architectural value from raw ft/in input strings. Returns null if both empty. */
export function buildArchValue(ftStr: string, inStr: string): string | null {
  if (ftStr === "" && inStr === "") return null;
  const ft = parseInt(ftStr, 10);
  const inches = parseFloat(inStr);
  return formatArch(
    isNaN(ft) ? 0 : Math.max(0, ft),
    isNaN(inches) ? 0 : Math.max(0, inches)
  );
}

/** Calculate area in sf from two dimension strings. Returns null if either is missing. */
export function calcAreaSf(
  w: string | null | undefined,
  h: string | null | undefined
): string | null {
  const wIn = parseToInches(w);
  const hIn = parseToInches(h);
  if (wIn === null || hIn === null) return null;
  const sf = (wIn / 12) * (hIn / 12);
  const rounded = parseFloat(sf.toFixed(4));
  return rounded === Math.floor(rounded)
    ? `${Math.floor(rounded)} sf`
    : `${rounded.toFixed(2)} sf`;
}
