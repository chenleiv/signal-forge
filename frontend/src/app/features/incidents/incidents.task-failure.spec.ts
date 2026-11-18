import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { provideRouter } from '@angular/router';
import { Subject, of } from 'rxjs';
import { Incidents } from './incidents';
import { ThreatStoreService } from '../../core/services/threat-store.service';
import { AuthService } from '../../core/services/auth';
import { CurrentUser } from '../../core/auth/permissions';
import { Incident } from '../../shared/models/threat.models';

const MANAGER: CurrentUser = { username: 'mia', display_name: 'Mia Manager', role: 'manager' };

const INCIDENT: Incident = {
  id: 'INC-8', title: 'Brute force on the VPN', severity: 'high', status: 'open', attack_type: 'BruteForce',
  source_region: 'US', event_count: 3, assigned_to: 'bob',
  created_at: '2026-11-18T10:00:00Z', updated_at: '2026-11-18T10:00:00Z',
  mitre_tags: [], notes: [], completed_tasks: [1],
} as Incident;

/** A failed response task update shows a message and puts that checkbox back. */
describe('Incidents: a failed response task update', () => {
  let replies: Subject<{ completed_tasks: number[] }>[];
  const store = {
    fetchIncidents: vi.fn(() => of([INCIDENT])),
    getUsers: vi.fn(() => of([])),
    getUserDirectory: vi.fn(() => of([])),
    updateIncidentTasks: vi.fn(() => {
      const reply = new Subject<{ completed_tasks: number[] }>();
      replies.push(reply);
      return reply;
    }),
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

  const tasks = (f: ReturnType<typeof open>) =>
    [...f.nativeElement.querySelectorAll('.task-item')] as HTMLElement[];
  const checked = (f: ReturnType<typeof open>) =>
    tasks(f).map(t => t.getAttribute('aria-checked'));
  const toast = (f: ReturnType<typeof open>) =>
    (f.nativeElement.querySelector('.toast') as HTMLElement | null)?.textContent?.trim();

  let logged: ReturnType<typeof vi.spyOn>;
  beforeEach(() => {
    vi.clearAllMocks();
    replies = [];
    logged = vi.spyOn(console, 'error').mockImplementation(() => undefined);
  });
  afterEach(() => logged.mockRestore());

  it('shows the server reason and unchecks a task that was checked before the server answered', () => {
    const f = open();
    expect(checked(f)).toEqual(['false', 'true', 'false', 'false', 'false']);

    tasks(f)[0].click();
    f.detectChanges();
    expect(store.updateIncidentTasks).toHaveBeenCalledWith('INC-8', [1, 0]);
    expect(tasks(f)[0].getAttribute('aria-checked')).toBe('true');  // optimistic

    replies[0].error(new HttpErrorResponse({ status: 403, error: { detail: 'Not allowed' } }));
    f.detectChanges();

    expect(checked(f)).toEqual(['false', 'true', 'false', 'false', 'false']);
    expect(toast(f)).toBe('Could not update INC-8: Not allowed');
    expect(logged).toHaveBeenCalledWith('[IncidentDetail] task update failed');
  });

  it('shows a generic message and checks again a task that was unchecked', () => {
    const f = open();

    tasks(f)[1].click();
    f.detectChanges();
    expect(tasks(f)[1].getAttribute('aria-checked')).toBe('false');  // optimistic

    replies[0].error(new HttpErrorResponse({ status: 500 }));
    f.detectChanges();

    expect(tasks(f)[1].getAttribute('aria-checked')).toBe('true');
    expect(toast(f)).toBe('Could not update INC-8. Please try again.');
  });

  it('rolls back only the failed task and keeps a later toggle', () => {
    const f = open();

    tasks(f)[0].click();
    f.detectChanges();
    tasks(f)[2].click();
    f.detectChanges();
    expect(checked(f)).toEqual(['true', 'true', 'true', 'false', 'false']);

    replies[0].error(new HttpErrorResponse({ status: 500 }));
    f.detectChanges();

    expect(checked(f)).toEqual(['false', 'true', 'true', 'false', 'false']);
  });

  it('a successful update keeps the new value and shows no message', () => {
    const f = open();

    tasks(f)[0].click();
    replies[0].next({ completed_tasks: [1, 0] });
    replies[0].complete();
    f.detectChanges();

    expect(tasks(f)[0].getAttribute('aria-checked')).toBe('true');
    expect(toast(f)).toBeUndefined();
    expect(logged).not.toHaveBeenCalled();
  });
});
