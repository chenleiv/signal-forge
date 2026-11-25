import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { ThreatTableComponent } from './threat-table.component';
import { ThreatStoreService } from '../../../core/services/threat-store.service';
import { ThreatStats } from '../../../shared/models/threat.models';

/** Exports read the filtered rows; JSON gets typed items, Markdown and CSV the display rows. */
describe('ThreatTableComponent: export', () => {
  let blobs: Blob[];

  const STATS = {
    top_ips: [
      { ip: '203.0.113.7', count: 12, score: 91, threat_level: 'critical' },
      { ip: '198.51.100.2', count: 3, score: 40, threat_level: 'medium' },
    ],
  } as unknown as ThreatStats;

  function create() {
    TestBed.configureTestingModule({
      imports: [ThreatTableComponent],
      providers: [{ provide: ThreatStoreService, useValue: { stats: signal(STATS) } }],
    });
    const fixture = TestBed.createComponent(ThreatTableComponent);
    fixture.detectChanges();
    return fixture;
  }

  beforeEach(() => {
    blobs = [];
    Object.assign(URL, {
      createObjectURL: vi.fn((b: Blob) => { blobs.push(b); return 'blob:test'; }),
      revokeObjectURL: vi.fn(),
    });
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
  });

  afterEach(() => vi.restoreAllMocks());

  it('JSON: typed items with snake_case keys, filtered rows only', async () => {
    const f = create();
    f.componentInstance.levelFilter.set('critical');
    f.componentInstance.exportJson();
    const doc = JSON.parse(await blobs[0].text());
    expect(doc.kind).toBe('threats');
    expect(doc.count).toBe(1);
    expect(doc.items).toEqual([{ ip: '203.0.113.7', avg_score: 91, events: 12, threat_level: 'critical' }]);
  });

  it('Markdown: a table of the display rows', async () => {
    const f = create();
    f.componentInstance.exportMarkdown();
    const md = await blobs[0].text();
    expect(md).toContain('| IP Address | Avg Score | Events | Level |');
    expect(md).toContain('| 203.0.113.7 | 91 | 12 | critical |');
    expect(md).toContain('| 198.51.100.2 | 40 | 3 | medium |');
  });

  it('CSV output for the threat table is unchanged by the neutralisation', async () => {
    const f = create();
    f.componentInstance.exportCsv();
    expect(await blobs[0].text()).toBe(
      '"IP Address","Avg Score","Events","Level"\n"203.0.113.7","91","12","critical"\n"198.51.100.2","40","3","medium"',
    );
  });
});
