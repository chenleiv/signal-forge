import {
  csvCell, downloadCsv, downloadJson, downloadMarkdown, markdownCell, toCsv, toJson, toMarkdown,
} from './export.utils';

describe('csvCell: formula neutralisation', () => {
  it.each([
    ['=', '=SUM(A1:A9)'],
    ['+', '+1+2'],
    ['-', '-2+3'],
    ['@', '@SUM(A1)'],
    ['tab', '\t=1+1'],
    ['carriage return', '\r=1+1'],
  ])('puts an apostrophe before a leading %s', (_name, value) => {
    expect(csvCell(value)).toBe(`"'${value}"`);
  });

  it('leaves a formula character that is not first alone', () => {
    expect(csvCell('a=b')).toBe('"a=b"');
    expect(csvCell('Alert: +1 failed login')).toBe('"Alert: +1 failed login"');
    expect(csvCell('x@example.com')).toBe('"x@example.com"');
  });

  it('leaves ordinary values unchanged', () => {
    expect(csvCell('203.0.113.7')).toBe('"203.0.113.7"');
    expect(csvCell('—')).toBe('"—"');
    expect(csvCell('42')).toBe('"42"');
  });

  it('turns empty, null and undefined into an empty quoted cell', () => {
    expect(csvCell('')).toBe('""');
    expect(csvCell(null)).toBe('""');
    expect(csvCell(undefined)).toBe('""');
  });

  it('does not cover leading spaces or full-width characters (documented gap)', () => {
    expect(csvCell(' =1+1')).toBe('" =1+1"');
    expect(csvCell('＝1+1')).toBe('"＝1+1"');
  });
});

describe('csvCell: quoting', () => {
  it('doubles embedded quotes', () => {
    expect(csvCell('say "hi"')).toBe('"say ""hi"""');
  });

  it('neutralises first, then doubles quotes', () => {
    expect(csvCell('="x"')).toBe(`"'=""x"""`);
  });

  it('keeps commas and newlines inside the quotes', () => {
    expect(csvCell('a,b\nc')).toBe('"a,b\nc"');
  });
});

describe('toCsv', () => {
  it('joins cells with commas and rows with \\n, header first', () => {
    expect(toCsv(['IP', 'Score'], [['203.0.113.7', '91'], ['198.51.100.2', '40']]))
      .toBe('"IP","Score"\n"203.0.113.7","91"\n"198.51.100.2","40"');
  });

  it('neutralises header cells too', () => {
    expect(toCsv(['=H'], [])).toBe(`"'=H"`);
  });
});

describe('markdownCell', () => {
  it.each([
    ['|', 'a|b', 'a\\|b'],
    ['backtick', 'a`b', 'a\\`b'],
    ['[', 'a[b', 'a\\[b'],
    [']', 'a]b', 'a\\]b'],
    ['<', '<script>', '\\<script>'],
    ['backslash', 'a\\b', 'a\\\\b'],
  ])('escapes %s', (_name, value, expected) => {
    expect(markdownCell(value)).toBe(expected);
  });

  it('escapes the backslash before the others, so an escape cannot be undone', () => {
    expect(markdownCell('\\|')).toBe('\\\\\\|');
  });

  it('turns every kind of line break into a space', () => {
    expect(markdownCell('a\nb\r\nc\rd')).toBe('a b c d');
  });

  it('cannot form a link', () => {
    expect(markdownCell('[x](javascript:alert(1))')).toBe('\\[x\\](javascript:alert(1))');
  });

  it('does not add a CSV apostrophe', () => {
    expect(markdownCell('=1+1')).toBe('=1+1');
  });

  it('turns null and undefined into an empty string', () => {
    expect(markdownCell(null)).toBe('');
    expect(markdownCell(undefined)).toBe('');
  });
});

describe('toMarkdown', () => {
  const at = new Date('2026-11-25T10:00:00.000Z');

  it('writes a title, the ISO time and a table', () => {
    expect(toMarkdown('Report', ['IP', 'Level'], [['203.0.113.7', 'high']], at)).toBe(
      [
        '# Report',
        '',
        'Generated 2026-11-25T10:00:00.000Z',
        '',
        '| IP | Level |',
        '| --- | --- |',
        '| 203.0.113.7 | high |',
        '',
      ].join('\n'),
    );
  });

  it('escapes the title, headers and cells, and keeps one line per row', () => {
    const md = toMarkdown('A|B', ['H|1'], [['x|y\nz']], at);
    expect(md.split('\n')).toEqual([
      '# A\\|B', '', 'Generated 2026-11-25T10:00:00.000Z', '', '| H\\|1 |', '| --- |', '| x\\|y z |', '',
    ]);
  });
});

describe('toJson', () => {
  const at = new Date('2026-11-25T10:00:00.000Z');

  it('wraps the items in an envelope with kind, time and count', () => {
    const items = [{ ip: '203.0.113.7', avg_score: 91, assigned_to: null }];
    const doc = JSON.parse(toJson('threats', items, at));
    expect(Object.keys(doc)).toEqual(['kind', 'generated_at', 'count', 'items']);
    expect(doc).toEqual({ kind: 'threats', generated_at: '2026-11-25T10:00:00.000Z', count: 1, items });
  });

  it('keeps numbers as numbers and null as null, with no CSV apostrophe', () => {
    const doc = JSON.parse(toJson('incidents', [{ n: 3, title: '=1+1', a: null }], at));
    expect(doc.items[0]).toEqual({ n: 3, title: '=1+1', a: null });
    expect(typeof doc.items[0].n).toBe('number');
  });

  it('count matches an empty list', () => {
    expect(JSON.parse(toJson('threats', [], at))).toMatchObject({ count: 0, items: [] });
  });
});

describe('download helpers', () => {
  let blobs: Blob[];
  let names: string[];

  beforeEach(() => {
    blobs = [];
    names = [];
    Object.assign(URL, {
      createObjectURL: vi.fn((b: Blob) => { blobs.push(b); return 'blob:test'; }),
      revokeObjectURL: vi.fn(),
    });
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      names.push(this.download);
    });
  });

  afterEach(() => vi.restoreAllMocks());

  it('downloadCsv: CSV type, file name and neutralised content', async () => {
    downloadCsv(['T'], [['=x']], 'incidents.csv');
    expect(names).toEqual(['incidents.csv']);
    expect(blobs[0].type).toBe('text/csv;charset=utf-8;');
    expect(await blobs[0].text()).toBe(`"T"\n"'=x"`);
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:test');
  });

  it('downloadJson: JSON type, file name and envelope', async () => {
    downloadJson('threats', [{ ip: '203.0.113.7' }], 'threats.json');
    expect(names).toEqual(['threats.json']);
    expect(blobs[0].type).toBe('application/json;charset=utf-8');
    expect(JSON.parse(await blobs[0].text())).toMatchObject({ kind: 'threats', count: 1 });
  });

  it('downloadMarkdown: Markdown type, file name and table', async () => {
    downloadMarkdown('Report', ['IP'], [['203.0.113.7']], 'threats.md');
    expect(names).toEqual(['threats.md']);
    expect(blobs[0].type).toBe('text/markdown;charset=utf-8');
    expect(await blobs[0].text()).toContain('| 203.0.113.7 |');
  });
});
