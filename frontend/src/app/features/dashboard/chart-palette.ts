// ECharts draws on a canvas and cannot read CSS variables, so the dashboard
// charts use this copy of the theme tokens from src/styles.scss. Keys are the
// CSS variable names without the leading "--".
// src/styles.contrast.spec.ts fails if a value here differs from styles.scss,
// and checks text entries for 4.5:1 and mark entries for 3:1.

export type ChartTheme = 'dark' | 'light';

/** Drawn as text: axis labels, titles, legends, the donut total. */
export const CHART_TEXT_TOKENS = ['c-text', 'c-text-2', 'c-muted'] as const;

/** Drawn as non-text marks: donut slices and bars. */
export const CHART_FILL_TOKENS = [
  'c-sev-critical-fill',
  'c-sev-high-fill',
  'c-sev-medium-fill',
  'c-sev-low-fill',
  'c-purple-fill',
  'c-success',
  'c-accent',
] as const;

/** Decorative only (grid lines), no contrast requirement. */
export const CHART_DECOR_TOKENS = ['c-border'] as const;

export type ChartToken =
  | (typeof CHART_TEXT_TOKENS)[number]
  | (typeof CHART_FILL_TOKENS)[number]
  | (typeof CHART_DECOR_TOKENS)[number];

export const CHART_PALETTE: Record<ChartTheme, Record<ChartToken, string>> = {
  dark: {
    'c-text': '#e7eef2',
    'c-text-2': '#a4b0b8',
    'c-muted': '#87939b',
    'c-border': '#232c38',
    'c-accent': '#06b6d4',
    'c-success': '#4ade80',
    'c-sev-critical-fill': '#f87171',
    'c-sev-high-fill': '#fb923c',
    'c-sev-medium-fill': '#fbbf24',
    'c-sev-low-fill': '#60a5fa',
    'c-purple-fill': '#c084fc',
  },
  light: {
    'c-text': '#1f2937',
    'c-text-2': '#4b5563',
    'c-muted': '#5b6575',
    'c-border': '#b8c2cf',
    'c-accent': '#0e7490',
    'c-success': '#166534',
    'c-sev-critical-fill': '#dc2626',
    'c-sev-high-fill': '#dc4f0a',
    'c-sev-medium-fill': '#c26a06',
    'c-sev-low-fill': '#2563eb',
    'c-purple-fill': '#9333ea',
  },
};
