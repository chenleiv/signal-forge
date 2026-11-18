import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { Incidents } from './incidents';
import { ThreatStoreService } from '../../core/services/threat-store.service';
import { AuthService } from '../../core/services/auth';
import { CurrentUser } from '../../core/auth/permissions';
import { Incident } from '../../shared/models/threat.models';

const MANAGER: CurrentUser = { username: 'mia', display_name: 'Mia Manager', role: 'manager' };

const INCIDENT: Incident = {
  id: 'INC-7', title: 'Brute force on the VPN', severity: 'high', status: 'open', attack_type: 'BruteForce',
  source_region: 'US', event_count: 3, assigned_to: 'bob',
  created_at: '2026-11-18T10:00:00Z', updated_at: '2026-11-18T10:00:00Z',
  mitre_tags: [], notes: [], completed_tasks: [],
} as Incident;

/** A failed status or assignee change shows a message and leaves the old value on screen. */
describe('Incidents: a failed incident update', () => {
  const store = {
    fetchIncidents: vi.fn(() => of([INCIDENT])),
    getUsers: vi.fn(() => of([
      { username: 'alice', display_name: 'Alice Chen', role: 'analyst' },
      { username: 'bob', display_name: 'Bob Martinez', role: 'analyst' },
    ])),
    getUserDirectory: vi.fn(() => of([])),
    patchIncident: vi.fn(),
  };

  function open() {
    TestBed.configureTestingModule({
      imports: [Incidents],
      providers: [
        provideRouter([]),
        { provide: ThreatStoreService, useValue: store },
        { provide: AuthService, useValue: { currentUser: signal(MANAGER) } },
      ],
    });
    const fixture = TestBed.createComponent(Incidents);
    fixture.detectChanges();
    (fixture.nativeElement.querySelector('.inc-row') as HTMLElement).click();
    fixture.detectChanges();
    return fixture;
  }

  const toast = (f: ReturnType<typeof open>) =>
    (f.nativeElement.querySelector('.toast') as HTMLElement | null)?.textContent?.trim();

  let logged: ReturnType<typeof vi.spyOn>;
  beforeEach(() => {
    vi.clearAllMocks();
    logged = vi.spyOn(console, 'error').mockImplementation(() => undefined);
  });
  afterEach(() => logged.mockRestore());

  it('assignee: shows the server reason and puts the select back to the current assignee', () => {
    store.patchIncident.mockReturnValue(throwError(() => new HttpErrorResponse({
      status: 409, error: { detail: 'The assignee changed; reload and try again' },
    })));
    const f = open();
    const select = f.nativeElement.querySelector('.assignee-select') as HTMLSelectElement;
    expect(select.value).toBe('bob');

    select.value = 'alice';
    select.dispatchEvent(new Event('change'));
    f.detectChanges();

    expect(store.patchIncident).toHaveBeenCalledWith('INC-7', { assigned_to: 'alice' });
    expect(select.value).toBe('bob');
    expect(f.componentInstance.selected()?.assigned_to).toBe('bob');
    expect(toast(f)).toBe('Could not update INC-7: The assignee changed; reload and try again');
    expect(logged).toHaveBeenCalledWith('[IncidentDetail] patch failed');
  });

  it('status: shows a generic message when the server gives no reason, and the status stays', () => {
    store.patchIncident.mockReturnValue(throwError(() => new HttpErrorResponse({ status: 500 })));
    const f = open();

    const investigating = [...f.nativeElement.querySelectorAll('.status-btn')]
      .find(b => (b as HTMLElement).textContent?.trim() === 'investigating') as HTMLButtonElement;
    investigating.click();
    f.detectChanges();

    expect(store.patchIncident).toHaveBeenCalledWith('INC-7', { status: 'investigating' });
    expect(toast(f)).toBe('Could not update INC-7. Please try again.');
    expect((f.nativeElement.querySelector('.status-btn.active') as HTMLElement).textContent?.trim()).toBe('open');
    expect(f.componentInstance.incidents()[0].status).toBe('open');
  });
});
