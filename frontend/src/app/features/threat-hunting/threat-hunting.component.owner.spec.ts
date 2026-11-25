import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { HttpErrorResponse } from '@angular/common/http';
import { provideRouter } from '@angular/router';
import { Observable, of, throwError } from 'rxjs';
import { ThreatHuntingComponent } from './threat-hunting.component';
import { ThreatStoreService } from '../../core/services/threat-store.service';
import { AuthService } from '../../core/services/auth';
import { CurrentUser } from '../../core/auth/permissions';
import { SavedHunt } from '../../shared/models/threat.models';

const SAVED: SavedHunt[] = [
  { id: 'h1', name: 'Mine',    query: {}, created_at: '2026-11-25T10:00:00Z', result_count: 1, created_by: 'alice' },
  { id: 'h2', name: 'Bobs',    query: {}, created_at: '2026-11-25T10:00:00Z', result_count: 2, created_by: 'bob' },
  { id: 'h3', name: 'Orphan',  query: {}, created_at: '2026-11-25T10:00:00Z', result_count: 3, created_by: null },
];

const ALICE: CurrentUser = { username: 'alice', display_name: 'Alice Chen', role: 'analyst' };
const MIRA: CurrentUser  = { username: 'mira',  display_name: 'Mira Cohen', role: 'manager' };
const ADMIN: CurrentUser = { username: 'admin', display_name: 'Sarah Kim',  role: 'admin' };

const httpError = (status: number, detail: string) =>
  throwError(() => new HttpErrorResponse({ status, error: { detail } }));

describe('ThreatHuntingComponent: saved hunt owners', () => {
  let deleteResult: () => Observable<unknown>;
  let saveResult: () => Observable<SavedHunt>;

  function create(user: CurrentUser) {
    TestBed.configureTestingModule({
      imports: [ThreatHuntingComponent],
      providers: [
        provideRouter([]),
        { provide: ThreatStoreService, useValue: {
          getSavedHunts: () => of(SAVED),
          runHunt: () => of({ results: [], total: 0 }),
          saveHunt: () => saveResult(),
          deleteHunt: () => deleteResult(),
        } },
        { provide: AuthService, useValue: { currentUser: signal(user) } },
      ],
    });
    const fixture = TestBed.createComponent(ThreatHuntingComponent);
    fixture.detectChanges();
    return fixture;
  }

  const deletable = (el: HTMLElement) =>
    [...el.querySelectorAll('.saved-item')]
      .filter(item => item.querySelector('.saved-del'))
      .map(item => item.querySelector('.saved-name')!.textContent!.trim());

  beforeEach(() => {
    deleteResult = () => of({ ok: true });
    saveResult = () => of(SAVED[0]);
  });

  it('shows the owner of every hunt, and "unknown" when there is none', () => {
    const el = create(ALICE).nativeElement as HTMLElement;
    const owners = [...el.querySelectorAll('.saved-owner')].map(o => o.textContent!.trim());
    expect(owners).toEqual(['by alice', 'by bob', 'by unknown']);
  });

  it('an analyst sees the delete button only on their own hunt', () => {
    expect(deletable(create(ALICE).nativeElement)).toEqual(['Mine']);
  });

  it('a manager gets no extra delete buttons', () => {
    expect(deletable(create(MIRA).nativeElement)).toEqual([]);
  });

  it('the admin sees the delete button on every hunt', () => {
    expect(deletable(create(ADMIN).nativeElement)).toEqual(['Mine', 'Bobs', 'Orphan']);
  });

  it('a 404 on delete removes the hunt from the list (it is already gone)', () => {
    deleteResult = () => httpError(404, 'Saved hunt not found');
    const fixture = create(ADMIN);
    fixture.componentInstance.deleteHunt('h2', new Event('click'));
    expect(fixture.componentInstance.savedHunts().map(h => h.id)).toEqual(['h1', 'h3']);
  });

  it('a 403 on delete keeps the hunt', () => {
    deleteResult = () => httpError(403, "Only the hunt's creator or an admin can delete this hunt");
    const fixture = create(ADMIN);
    fixture.componentInstance.deleteHunt('h2', new Event('click'));
    expect(fixture.componentInstance.savedHunts().map(h => h.id)).toEqual(['h1', 'h2', 'h3']);
  });

  it('a 409 on save shows the server message', () => {
    const message = 'You have 20 saved hunts, the most allowed. Delete one of yours first';
    saveResult = () => httpError(409, message);
    const fixture = create(ALICE);
    fixture.componentInstance.showSave.set(true);
    fixture.componentInstance.saveName.set('one more');
    fixture.componentInstance.saveHunt();
    fixture.detectChanges();
    const error = (fixture.nativeElement as HTMLElement).querySelector('.save-error')!;
    expect(error.textContent!.trim()).toBe(message);
    expect(error.getAttribute('role')).toBe('alert');
    expect(fixture.componentInstance.savedHunts()).toHaveLength(3);
  });
});
