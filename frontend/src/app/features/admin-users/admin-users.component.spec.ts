import { ComponentFixture, TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { Observable, Subject, of, throwError } from 'rxjs';
import { AdminUsersComponent } from './admin-users.component';
import { ThreatStoreService } from '../../core/services/threat-store.service';
import { AuthService } from '../../core/services/auth';
import { CurrentUser } from '../../core/auth/permissions';
import { UserSummary } from '../../shared/models/threat.models';

const ADMIN: CurrentUser = { username: 'admin', display_name: 'Sarah Kim', role: 'admin' };
const ALICE: CurrentUser = { username: 'alice', display_name: 'Alice Chen', role: 'analyst' };
const USERS: UserSummary[] = [ADMIN, ALICE, { username: 'bob', display_name: 'Bob Martinez', role: 'analyst' }];

describe('AdminUsersComponent', () => {
  const user = signal<CurrentUser | null>(ADMIN);
  const store = {
    getUsers: vi.fn(() => of(USERS)),
    createUser: vi.fn((u: { username: string; display_name: string; role: 'analyst' | 'admin' }) =>
      of({ username: u.username, display_name: u.display_name, role: u.role })),
    updateUser: vi.fn((username: string, patch: { role?: 'admin' | 'analyst' }) =>
      of({ ...USERS.find(u => u.username === username)!, ...(patch.role ? { role: patch.role } : {}) })),
    deleteUser: vi.fn(() => of({ ok: true })),
  };

  function create() {
    TestBed.configureTestingModule({
      imports: [AdminUsersComponent],
      providers: [{ provide: ThreatStoreService, useValue: store }, { provide: AuthService, useValue: { currentUser: user } }],
    });
    const fixture = TestBed.createComponent(AdminUsersComponent);
    fixture.detectChanges();
    return fixture;
  }

  beforeEach(() => { vi.clearAllMocks(); user.set(ADMIN); });

  it('lists users and marks the current admin, with no delete button for self', () => {
    const el = create().nativeElement as HTMLElement;
    const rows = [...el.querySelectorAll('tbody tr')];
    expect(rows).toHaveLength(3);
    expect(rows[0].textContent).toContain('you');
    expect(rows[0].querySelector('.btn-del')).toBeNull();
    expect(rows[1].querySelector('.btn-del')).not.toBeNull();
  });

  it('no Reset password on your own row (that is in Settings, with the current password)', () => {
    const el = create().nativeElement as HTMLElement;
    const [ownRow, aliceRow] = [...el.querySelectorAll('tbody tr')];
    const hasReset = (row: Element) => [...row.querySelectorAll('button')].some(b => b.textContent?.includes('Reset'));
    expect(hasReset(ownRow)).toBe(false);
    expect(hasReset(aliceRow)).toBe(true);
  });

  it('creates a user', () => {
    const c = create().componentInstance;
    c.newUsername.set(' carol '); c.newDisplayName.set('Carol'); c.newPassword.set('long-enough-pass');
    c.create();
    expect(store.createUser).toHaveBeenCalledWith({ username: 'carol', display_name: 'Carol', role: 'analyst', password: 'long-enough-pass' });
    expect(c.users().map(u => u.username)).toContain('carol');
    expect(c.newPassword()).toBe('');  // the password does not linger in the form
  });

  it('deletes only after an in-page confirmation', () => {
    const c = create().componentInstance;
    c.askDelete('bob');
    expect(store.deleteUser).not.toHaveBeenCalled();
    c.confirmDelete();
    expect(store.deleteUser).toHaveBeenCalledWith('bob');
    expect(c.users().map(u => u.username)).not.toContain('bob');
  });

  it('never deletes the current user, even if the handler is called directly', () => {
    const c = create().componentInstance;
    c.askDelete('admin');
    c.pendingDelete.set('admin');
    c.confirmDelete();
    expect(store.deleteUser).not.toHaveBeenCalled();
  });

  it('shows the server reason when a change is refused', () => {
    store.updateUser.mockReturnValueOnce(throwError(() => new HttpErrorResponse({
      status: 404, error: { detail: 'User not found' } })));
    const fixture = create();
    fixture.componentInstance.changeRole(USERS[2], 'manager');
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).querySelector('[role=alert]')?.textContent).toContain('User not found');
  });

  describe('exactly one admin', () => {
    it('the admin row has no role picker and no delete; the admin role is never offered', () => {
      const el = create().nativeElement as HTMLElement;
      const [adminRow, aliceRow] = [...el.querySelectorAll('tbody tr')];
      expect(adminRow.querySelector('.role-select')).toBeNull();
      expect(adminRow.querySelector('.btn-del')).toBeNull();
      const options = [...el.querySelectorAll('option')].map(o => o.value);
      expect(options).not.toContain('admin');
      expect(aliceRow.querySelector('.role-select')).not.toBeNull();
    });

    it('handlers refuse admin-role changes and deleting the admin, even if called directly', () => {
      const c = create().componentInstance;
      c.changeRole(USERS[0], 'analyst');   // demote the admin
      c.changeRole(USERS[2], 'admin');     // grant admin
      c.askDelete('admin');
      c.pendingDelete.set('admin');        // as if the confirmation had been forced open
      c.confirmDelete();
      c.newUsername.set('eve'); c.newDisplayName.set('Eve'); c.newPassword.set('long-enough-pass');
      c.newRole.set('admin');
      c.create();
      expect(store.updateUser).not.toHaveBeenCalled();
      expect(store.deleteUser).not.toHaveBeenCalled();
      expect(store.createUser).not.toHaveBeenCalled();
    });
  });

  it('handlers do nothing for a non-admin', () => {
    user.set(ALICE);
    const c = create().componentInstance;
    c.newUsername.set('x'); c.newDisplayName.set('x'); c.newPassword.set('long-enough-pass');
    c.create();
    c.changeRole(USERS[2], 'admin');
    c.startReset('bob'); c.resetFor.set('bob'); c.submitReset();
    c.askDelete('bob'); c.pendingDelete.set('bob'); c.confirmDelete();
    expect(store.createUser).not.toHaveBeenCalled();
    expect(store.updateUser).not.toHaveBeenCalled();
    expect(store.deleteUser).not.toHaveBeenCalled();
  });

  describe('as a manager', () => {
    const MIRA: CurrentUser = { username: 'mira', display_name: 'Mira Cohen', role: 'manager' };
    beforeEach(() => user.set(MIRA));

    it('offers password reset for analysts only, and nothing else', () => {
      const el = create().nativeElement as HTMLElement;
      const rows = [...el.querySelectorAll('tbody tr')];
      const resetIn = (i: number) => [...rows[i].querySelectorAll('button')].some(b => b.textContent?.includes('Reset'));
      expect(resetIn(0)).toBe(false);  // admin
      expect(resetIn(1)).toBe(true);   // alice (analyst)
      expect(resetIn(2)).toBe(true);   // bob (analyst)
      expect(el.querySelector('.role-select')).toBeNull();
      expect(el.querySelector('.btn-del')).toBeNull();
      expect(el.textContent).not.toContain('New user');
    });

    it('handlers refuse what a manager may not do, even if called directly', () => {
      const c = create().componentInstance;
      c.startReset('admin');
      expect(c.resetFor()).toBeNull();
      c.resetFor.set('admin');           // as if the control had been forced open
      c.resetPassword.set('new-password-123');
      c.submitReset();
      c.changeRole(USERS[1], 'admin');
      c.askDelete('bob');
      c.confirmDelete();
      c.newUsername.set('eve'); c.newDisplayName.set('Eve'); c.newPassword.set('long-enough-pass');
      c.create();
      expect(store.updateUser).not.toHaveBeenCalled();
      expect(store.deleteUser).not.toHaveBeenCalled();
      expect(store.createUser).not.toHaveBeenCalled();
    });

    it('resets an analyst\'s password', () => {
      const c = create().componentInstance;
      c.startReset('alice');
      c.resetPassword.set('new-password-123');
      c.submitReset();
      expect(store.updateUser).toHaveBeenCalledWith('alice', { password: 'new-password-123' });
    });
  });
});

describe('AdminUsersComponent states and keyboard', () => {
  const ADMIN_U: CurrentUser = { username: 'admin', display_name: 'Sarah Kim', role: 'admin' };
  const LIST: UserSummary[] = [
    ADMIN_U,
    { username: 'alice', display_name: 'Alice Chen', role: 'analyst' },
    { username: 'bob', display_name: 'Bob Martinez', role: 'analyst' },
  ];
  const user = signal<CurrentUser | null>(ADMIN_U);
  const store = {
    getUsers: vi.fn((): Observable<UserSummary[]> => of(LIST)),
    createUser: vi.fn(),
    updateUser: vi.fn((username: string) => of(LIST.find(u => u.username === username)!)),
    deleteUser: vi.fn(() => of({ ok: true })),
  };

  function create() {
    TestBed.configureTestingModule({
      imports: [AdminUsersComponent],
      providers: [{ provide: ThreatStoreService, useValue: store }, { provide: AuthService, useValue: { currentUser: user } }],
    });
    const fixture = TestBed.createComponent(AdminUsersComponent);
    document.body.appendChild(fixture.nativeElement);   // focus needs the element in the document
    fixture.detectChanges();
    return fixture;
  }

  async function settle(fixture: ComponentFixture<AdminUsersComponent>) {
    fixture.detectChanges();
    await fixture.whenStable();
  }

  beforeEach(() => {
    vi.clearAllMocks();
    store.getUsers.mockImplementation(() => of(LIST));
    user.set(ADMIN_U);
  });

  it('shows a busy loading state until the list arrives, then the table and a count', () => {
    const pending = new Subject<UserSummary[]>();
    store.getUsers.mockReturnValueOnce(pending);
    const fixture = create();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('[role=status][aria-busy=true]')?.textContent).toContain('Loading users');
    expect(el.querySelector('table')).toBeNull();
    pending.next(LIST);
    fixture.detectChanges();
    expect(el.querySelector('[aria-busy=true]')).toBeNull();
    expect(el.querySelectorAll('tbody tr')).toHaveLength(3);
    expect(el.querySelector('.count')?.textContent?.trim()).toBe('3 accounts');
  });

  it('shows an empty state when there are no users', () => {
    store.getUsers.mockReturnValueOnce(of([]));
    const el = create().nativeElement as HTMLElement;
    expect(el.querySelector('.empty')?.textContent).toContain('No users yet');
    expect(el.querySelector('table')).toBeNull();
  });

  it('offers Retry after a failed load, and Retry loads the list and focuses the Accounts heading', async () => {
    store.getUsers.mockReturnValueOnce(throwError(() => new HttpErrorResponse({ status: 500 })));
    const fixture = create();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('[role=alert]')?.textContent).toContain('Could not load users');
    expect(el.querySelector('table')).toBeNull();
    (el.querySelector('#retry-load') as HTMLButtonElement).click();
    await settle(fixture);
    expect(store.getUsers).toHaveBeenCalledTimes(2);
    expect(el.querySelectorAll('tbody tr')).toHaveLength(3);
    expect(document.activeElement?.id).toBe('accounts-title');
  });

  it('a failed Retry keeps the Retry button focused', async () => {
    store.getUsers.mockReturnValue(throwError(() => new HttpErrorResponse({ status: 500 })));
    const fixture = create();
    (fixture.nativeElement.querySelector('#retry-load') as HTMLButtonElement).click();
    await settle(fixture);
    expect(document.activeElement?.id).toBe('retry-load');
  });

  it('row action buttons name the user they act on', () => {
    const el = create().nativeElement as HTMLElement;
    expect(el.querySelector('#reset-btn-alice')?.getAttribute('aria-label')).toBe('Reset password for alice');
    expect(el.querySelector('#delete-btn-alice')?.getAttribute('aria-label')).toBe('Delete alice');
  });

  it('opening a reset focuses the field; Escape closes it, clears it and returns focus', async () => {
    const fixture = create();
    const el = fixture.nativeElement as HTMLElement;
    (el.querySelector('#reset-btn-alice') as HTMLButtonElement).click();
    await settle(fixture);
    const input = el.querySelector('#reset-password') as HTMLInputElement;
    expect(document.activeElement).toBe(input);
    fixture.componentInstance.resetPassword.set('typed-but-cancelled');
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    await settle(fixture);
    expect(fixture.componentInstance.resetFor()).toBeNull();
    expect(fixture.componentInstance.resetPassword()).toBe('');
    expect(document.activeElement?.id).toBe('reset-btn-alice');
  });

  it('Enter in the reset field submits the reset', async () => {
    const fixture = create();
    const el = fixture.nativeElement as HTMLElement;
    fixture.componentInstance.startReset('alice');
    await settle(fixture);
    fixture.componentInstance.resetPassword.set('new-password-123');
    el.querySelector('form.confirm')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await settle(fixture);
    expect(store.updateUser).toHaveBeenCalledWith('alice', { password: 'new-password-123' });
    expect(document.activeElement?.id).toBe('reset-btn-alice');
  });

  it('a delete confirmation focuses Cancel; Escape closes it and returns focus to Delete', async () => {
    const fixture = create();
    const el = fixture.nativeElement as HTMLElement;
    (el.querySelector('#delete-btn-bob') as HTMLButtonElement).click();
    await settle(fixture);
    expect(document.activeElement?.id).toBe('cancel-delete');
    document.activeElement!.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    await settle(fixture);
    expect(fixture.componentInstance.pendingDelete()).toBeNull();
    expect(store.deleteUser).not.toHaveBeenCalled();
    expect(document.activeElement?.id).toBe('delete-btn-bob');
  });

  it('after a delete, focus moves to the Accounts heading', async () => {
    const fixture = create();
    fixture.componentInstance.askDelete('bob');
    await settle(fixture);
    fixture.componentInstance.confirmDelete();
    await settle(fixture);
    expect(store.deleteUser).toHaveBeenCalledWith('bob');
    expect(document.activeElement?.id).toBe('accounts-title');
  });
});
