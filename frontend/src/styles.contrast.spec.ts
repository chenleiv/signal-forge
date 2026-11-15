// Checks the theme palette in src/styles.scss against WCAG AA:
// text tokens 4.5:1 on the page background and the panel, non-text
// (-fill) tokens 3:1, --c-on-sev 4.5:1 on each severity background, and
// --c-on-accent 4.5:1 on --c-accent and --c-accent-hover.
// Also checks the ECharts palette mirror in chart-palette.ts.

import {
  CHART_DECOR_TOKENS,
  CHART_FILL_TOKENS,
  CHART_PALETTE,
  CHART_TEXT_TOKENS,
} from './app/features/dashboard/chart-palette';

interface NodeFs {
  readFileSync(path: string, encoding: string): string;
  readdirSync(path: string, options: { recursive: true }): string[];
}
interface NodeProcess { cwd(): string; getBuiltinModule(id: string): unknown; }

const proc = (globalThis as unknown as { process: NodeProcess }).process;
const fs = proc.getBuiltinModule('node:fs') as NodeFs;

function srcDir(): string {
  for (const dir of ['src', 'frontend/src']) {
    try {
      fs.readFileSync(`${proc.cwd()}/${dir}/styles.scss`, 'utf8');
      return `${proc.cwd()}/${dir}`;
    } catch {
      // try the next candidate
    }
  }
  throw new Error('src/styles.scss not found from ' + proc.cwd());
}

const SRC = srcDir();

function readStyles(): string {
  return fs.readFileSync(`${SRC}/styles.scss`, 'utf8');
}

function themeVars(css: string, theme: 'dark' | 'light'): Record<string, string> {
  const block = css.match(new RegExp(`:root\\[data-theme="${theme}"\\]\\s*\\{([^}]*)\\}`));
  if (!block) throw new Error(`no ${theme} theme block`);
  const vars: Record<string, string> = {};
  for (const m of block[1].matchAll(/--([\w-]+)\s*:\s*(#[0-9a-fA-F]{6})\s*;/g)) {
    vars[m[1]] = m[2].toLowerCase();
  }
  return vars;
}

function luminance(hex: string): number {
  const channel = (i: number) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(1) + 0.7152 * channel(3) + 0.0722 * channel(5);
}

function ratio(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

const TEXT = [
  'c-text', 'c-text-2', 'c-muted', 'c-accent', 'c-success', 'c-warning',
  'c-sev-critical', 'c-sev-high', 'c-sev-medium', 'c-sev-low', 'c-purple',
];
const FILL = [
  'c-sev-critical-fill', 'c-sev-high-fill', 'c-sev-medium-fill', 'c-sev-low-fill', 'c-purple-fill',
];
const SEV_BG = ['c-sev-critical', 'c-sev-high', 'c-sev-medium', 'c-sev-low'];

describe('theme palette contrast (WCAG AA)', () => {
  const css = readStyles();

  for (const theme of ['dark', 'light'] as const) {
    describe(theme, () => {
      const vars = themeVars(css, theme);
      const surfaces = ['c-bg', 'c-panel'];

      it('defines every palette token', () => {
        for (const name of [...surfaces, ...TEXT, ...FILL, 'c-on-sev', 'c-accent-hover', 'c-on-accent']) {
          expect(vars[name], `--${name}`).toMatch(/^#[0-9a-f]{6}$/);
        }
      });

      for (const name of TEXT) {
        it(`--${name} reaches 4.5:1 as text`, () => {
          for (const bg of surfaces) {
            expect(ratio(vars[name], vars[bg]), `--${name} on --${bg}`).toBeGreaterThanOrEqual(4.5);
          }
        });
      }

      for (const name of FILL) {
        it(`--${name} reaches 3:1 as a non-text mark`, () => {
          for (const bg of surfaces) {
            expect(ratio(vars[name], vars[bg]), `--${name} on --${bg}`).toBeGreaterThanOrEqual(3);
          }
        });
      }

      it('--c-on-sev reaches 4.5:1 on every severity background', () => {
        for (const bg of SEV_BG) {
          expect(ratio(vars['c-on-sev'], vars[bg]), `--c-on-sev on --${bg}`).toBeGreaterThanOrEqual(4.5);
        }
      });

      it('--c-on-accent reaches 4.5:1 on the accent and the accent hover fills', () => {
        for (const bg of ['c-accent', 'c-accent-hover']) {
          expect(ratio(vars['c-on-accent'], vars[bg]), `--c-on-accent on --${bg}`).toBeGreaterThanOrEqual(4.5);
        }
      });
    });
  }
});

// Sass color functions cannot read a CSS variable: rgba($accent, .1) compiles
// to rgba(var(--c-accent), .1), which browsers drop. Use color-mix() instead.
describe('Sass color functions on CSS-variable tokens', () => {
  it('no component applies rgba() or similar to a var()-based token', () => {
    const tokens = fs.readFileSync(`${SRC}/styles/_tokens.scss`, 'utf8');
    const varTokens = [...tokens.matchAll(/^\$([\w-]+):\s*(var\(|\$)/gm)].map(m => m[1]);
    expect(varTokens.length).toBeGreaterThan(0);

    const fn = /\b(rgba?|lighten|darken|mix|transparentize|fade-out|fade-in|opacify|adjust-hue|saturate|desaturate)\(\s*\$([\w-]+)/g;
    const offenders: string[] = [];
    for (const rel of fs.readdirSync(SRC, { recursive: true })) {
      if (!rel.endsWith('.scss')) continue;
      const text = fs.readFileSync(`${SRC}/${rel}`, 'utf8');
      text.split('\n').forEach((line, i) => {
        for (const m of line.matchAll(fn)) {
          if (varTokens.includes(m[2])) offenders.push(`${rel}:${i + 1} ${m[0]}`);
        }
      });
    }
    expect(offenders).toEqual([]);
  });
});

// ECharts cannot read CSS variables, so chart-palette.ts keeps a copy of the
// tokens per theme. It must match styles.scss exactly and meet the same ratios.
describe('ECharts palette mirror (chart-palette.ts)', () => {
  const css = readStyles();

  for (const theme of ['dark', 'light'] as const) {
    describe(theme, () => {
      const vars = themeVars(css, theme);
      const pal = CHART_PALETTE[theme];
      const surfaces = ['c-bg', 'c-panel'];

      it('lists every mirrored token in exactly one role', () => {
        const roles = [...CHART_TEXT_TOKENS, ...CHART_FILL_TOKENS, ...CHART_DECOR_TOKENS];
        expect(new Set(roles).size).toBe(roles.length);
        expect(Object.keys(pal).sort()).toEqual([...roles].sort());
      });

      it('matches the CSS tokens in styles.scss', () => {
        for (const [name, value] of Object.entries(pal)) {
          expect(vars[name], `--${name} missing from styles.scss`).toBeDefined();
          expect(value.toLowerCase(), `chart ${name} drifted from --${name}`).toBe(vars[name]);
        }
      });

      for (const name of CHART_TEXT_TOKENS) {
        it(`chart text ${name} reaches 4.5:1`, () => {
          for (const bg of surfaces) {
            expect(ratio(pal[name], vars[bg]), `${name} on --${bg}`).toBeGreaterThanOrEqual(4.5);
          }
        });
      }

      for (const name of CHART_FILL_TOKENS) {
        it(`chart mark ${name} reaches 3:1`, () => {
          for (const bg of surfaces) {
            expect(ratio(pal[name], vars[bg]), `${name} on --${bg}`).toBeGreaterThanOrEqual(3);
          }
        });
      }
    });
  }
});
