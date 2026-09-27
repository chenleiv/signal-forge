import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { of, throwError } from 'rxjs';
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
