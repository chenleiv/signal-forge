import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';
import { Incidents } from './incidents';
import { ThreatStoreService } from '../../core/services/threat-store.service';
import { AuthService } from '../../core/services/auth';
import { Incident } from '../../shared/models/threat.models';

/** JSON gets typed items (ISO time, null assignee); CSV neutralises formula cells; Markdown escapes. */
describe('Incidents: export', () => {
  let blobs: Blob[];

  const base: Incident = {
    id: 'INC-1', title: 'Brute force against the VPN gateway', severity: 'critical', status: 'open',
    attack_type: 'BruteForce', source_region: 'EU', event_count: 7, assigned_to: null,
    created_at: '2026-11-25T10:00:00.000Z', updated_at: '2026-11-25T10:00:00.000Z',
    mitre_tags: [], notes: [], completed_tasks: [],
  };
  const INCIDENTS: Incident[] = [
    base,
    { ...base, id: 'INC-2', title: '-2+3 |[x](y)', severity: 'low', status: 'closed', assigned_to: 'analyst' },
  ];

  function create() {
    TestBed.configureTestingModule({
      imports: [Incidents],
      providers: [
        provideRouter([]),
        { provide: ThreatStoreService, useValue: {
          fetchIncidents: () => of(INCIDENTS), getUsers: () => of([]), getUserDirectory: () => of([]),
        } },
        { provide: AuthService, useValue: { currentUser: signal(null) } },
      ],
    });
    const fixture = TestBed.createComponent(Incidents);
    fixture.componentInstance.incidents.set(INCIDENTS);
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

  it('JSON: typed items, ISO created_at, null when unassigned, no apostrophe', async () => {
    const f = create();
    f.componentInstance.exportJson();
    const doc = JSON.parse(await blobs[0].text());
    expect(doc.kind).toBe('incidents');
    expect(doc.count).toBe(2);
    expect(doc.items[0]).toEqual({
      id: 'INC-1', title: 'Brute force against the VPN gateway', severity: 'critical', status: 'open',
      attack_type: 'BruteForce', source_region: 'EU', event_count: 7, assigned_to: null,
      created_at: '2026-11-25T10:00:00.000Z',
    });
    expect(doc.items[1].title).toBe('-2+3 |[x](y)');
    expect(doc.items[1].assigned_to).toBe('analyst');
  });

  it('JSON follows the filters', async () => {
    const f = create();
    f.componentInstance.statusFilter.set('closed');
    f.componentInstance.exportJson();
    const doc = JSON.parse(await blobs[0].text());
    expect(doc.items.map((i: { id: string }) => i.id)).toEqual(['INC-2']);
  });

  it('CSV: a title starting with a formula character gets an apostrophe', async () => {
    const f = create();
    f.componentInstance.exportCsv();
    const lines = (await blobs[0].text()).split('\n');
    expect(lines[1]).toContain('"Brute force against the VPN gateway"');
    expect(lines[2]).toContain(`"'-2+3 |[x](y)"`);
  });

  it('Markdown: the title cell is escaped and stays in its row', async () => {
    const f = create();
    f.componentInstance.exportMarkdown();
    const md = await blobs[0].text();
    expect(md).toContain('# SignalForge — Incident Report');
    expect(md).toContain('| INC-2 | -2+3 \\|\\[x\\](y) | low | closed |');
  });
});
