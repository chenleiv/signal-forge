import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';
import { IncidentDetailComponent } from './incident-detail.component';
import { ThreatStoreService } from '../../../core/services/threat-store.service';
import { AuthService } from '../../../core/services/auth';
import { CurrentUser } from '../../../core/auth/permissions';
import { Incident } from '../../../shared/models/threat.models';

const ALICE: CurrentUser = { username: 'alice', display_name: 'Alice Chen', role: 'analyst' };

function incident(assigned_to: string | null): Incident {
  return {
    id: 'INC-1', title: 't', severity: 'high', status: 'open', attack_type: 'SQLi',
    source_region: 'US', event_count: 1, assigned_to, created_at: '2026-09-26T10:00:00Z', updated_at: '2026-09-26T10:00:00Z',
    mitre_tags: [], notes: [], completed_tasks: [],
  } as Incident;
}

/**
 * Controls use aria-disabled (not disabled) so tooltips work, which means
 * they stay clickable. Every handler must re-check the permission.
 */
describe('IncidentDetailComponent: handlers ignore forbidden clicks', () => {
  const store = {
    getUsers: vi.fn(() => of([])),
    patchIncident: vi.fn((_id: string, p: Partial<Incident>) => of({ ...incident('bob'), ...p })),
    updateIncidentTasks: vi.fn(() => of({ completed_tasks: [] })),
    addIncidentNote: vi.fn(() => of({ author: 'alice', text: 'x', at: '2026-09-26T10:00:00Z' })),
  };

  function create(owner: string | null) {
    TestBed.configureTestingModule({
      imports: [IncidentDetailComponent],
      providers: [
        provideRouter([]),
        { provide: ThreatStoreService, useValue: store },
        { provide: AuthService, useValue: { currentUser: signal(ALICE) } },
      ],
    });
    const fixture = TestBed.createComponent(IncidentDetailComponent);
    fixture.componentRef.setInput('incident', incident(owner));
    fixture.detectChanges();
    return fixture;
  }

  beforeEach(() => vi.clearAllMocks());

  it('clicking a status button on someone else\'s incident sends nothing', () => {
    const fixture = create('bob');
    const btn = fixture.nativeElement.querySelector('.status-btn:not(.active)') as HTMLButtonElement;
    expect(btn.getAttribute('aria-disabled')).toBe('true');
    expect(btn.title).toBe('Only the assignee or an admin can change this incident');

    btn.click();

    expect(store.patchIncident).not.toHaveBeenCalled();
  });

  it('task, note and assignment handlers also do nothing without permission', () => {
    const c = create('bob').componentInstance;
    c.toggleTask(0);
    c.newNote.set('hello');
    c.addNote();
    c.updateAssignee('alice');
    c.takeCase();
    expect(store.updateIncidentTasks).not.toHaveBeenCalled();
    expect(store.addIncidentNote).not.toHaveBeenCalled();
    expect(store.patchIncident).not.toHaveBeenCalled();
    expect(c.completedTasks().size).toBe(0);  // no optimistic local change either
  });

  it('the assignee\'s status click is sent', () => {
    const fixture = create('alice');
    (fixture.nativeElement.querySelector('.status-btn:not(.active)') as HTMLButtonElement).click();
    expect(store.patchIncident).toHaveBeenCalledOnce();
  });

  it('shows Take case on an unassigned incident and takes it for the user', () => {
    const fixture = create(null);
    const take = fixture.nativeElement.querySelector('.take-btn') as HTMLButtonElement;
    expect(take).not.toBeNull();
    expect(fixture.nativeElement.querySelector('.assignee-select')).toBeNull();  // analyst: no dropdown

    take.click();

    expect(store.patchIncident).toHaveBeenCalledWith('INC-1', { assigned_to: 'alice' });
  });

  it('no Take case on an assigned incident', () => {
    expect(create('bob').nativeElement.querySelector('.take-btn')).toBeNull();
  });
});
