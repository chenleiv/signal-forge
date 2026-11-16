import { ChangeDetectionStrategy, Component, DestroyRef, Injector, afterNextRender, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { HttpErrorResponse } from '@angular/common/http';
import { ThreatStoreService } from '../../core/services/threat-store.service';
import { AuthService } from '../../core/services/auth';
import { canCreateUser, canDeleteUser, canManageUsers, canUpdateUser } from '../../core/auth/permissions';
import { UserRole, UserSummary } from '../../shared/models/threat.models';

/**
 * Admin-only user management: create users, change roles, reset passwords,
 * delete (soft delete on the server). The route is guarded, and every
 * handler re-checks the permission; the server enforces all of it anyway.
 */
@Component({
  selector: 'app-admin-users',
  standalone: true,
  templateUrl: './admin-users.component.html',
  styleUrl: './admin-users.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AdminUsersComponent {
  private store      = inject(ThreatStoreService);
  private auth       = inject(AuthService);
  private destroyRef = inject(DestroyRef);
  private injector   = inject(Injector);

  /** Roles an admin can give. Never 'admin': there is exactly one admin. */
  readonly roles: UserRole[] = ['analyst', 'manager'];
  readonly me      = computed(() => this.auth.currentUser()?.username ?? null);
  /** Create, change role, delete: admin only. */
  readonly allowed = computed(() => canManageUsers(this.auth.currentUser()).allowed);
  /** Reset this user's password? Admins: anyone. Managers: analysts only. */
  /** Never your own row: your own password changes in Settings. */
  readonly canReset = (u: UserSummary | undefined) =>
    canUpdateUser(this.auth.currentUser(), u, { password: '' }).allowed;
  /** The admin's own row: role fixed, not deletable. */
  readonly canChangeRole = (u: UserSummary) => this.allowed() && u.role !== 'admin';
  readonly canDelete = (u: UserSummary) => canDeleteUser(this.auth.currentUser(), u).allowed;

  users   = signal<UserSummary[]>([]);
  loading = signal(true);
  /** The user list could not be loaded; the Accounts card offers Retry. */
  loadFailed = signal(false);
  error   = signal<string | null>(null);
  notice  = signal<string | null>(null);

  // Create form
  newUsername    = signal('');
  newDisplayName = signal('');
  newRole        = signal<UserRole>('analyst');
  newPassword    = signal('');

  // Inline actions
  resetFor        = signal<string | null>(null);
  resetPassword   = signal('');
  pendingDelete   = signal<string | null>(null);

  constructor() {
    this.load();
  }

  /** Load again after a failed load. Focus returns to the Accounts heading. */
  retry() {
    if (this.loading()) return;
    this.load(true);
  }

  private load(focusAfter = false) {
    this.loading.set(true);
    this.loadFailed.set(false);
    this.store.getUsers()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: users => { this.users.set(users); this.loading.set(false); if (focusAfter) this.focusAfterRender('accounts-title'); },
        error: () => { this.loadFailed.set(true); this.loading.set(false); if (focusAfter) this.focusAfterRender('retry-load'); },
      });
  }

  create() {
    if (!canCreateUser(this.auth.currentUser(), { role: this.newRole() }).allowed) return;
    this.store.createUser({
      username: this.newUsername().trim(),
      display_name: this.newDisplayName().trim(),
      role: this.newRole(),
      password: this.newPassword(),
    })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: user => {
          this.users.update(list => [...list, user]);
          this.newUsername.set(''); this.newDisplayName.set(''); this.newPassword.set(''); this.newRole.set('analyst');
          this.done(`Created ${user.username}`);
        },
        error: e => this.fail(e),
      });
  }

  changeRole(user: UserSummary, role: UserRole) {
    if (role === user.role || !canUpdateUser(this.auth.currentUser(), user, { role }).allowed) return;
    this.store.updateUser(user.username, { role })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: updated => {
          this.users.update(list => list.map(u => (u.username === updated.username ? updated : u)));
          this.done(`${updated.username} is now ${updated.role}; their sessions were signed out`);
        },
        error: e => this.fail(e),
      });
  }

  // Handlers re-check permissions: hidden controls are UX, not a boundary.
  startReset(username: string) {
    if (!this.canReset(this.findUser(username))) return;
    this.pendingDelete.set(null);
    this.resetFor.set(username);
    this.resetPassword.set('');
    this.focusAfterRender('reset-password');
  }

  submitReset() {
    const username = this.resetFor();
    if (!username || !this.canReset(this.findUser(username))) return;
    this.store.updateUser(username, { password: this.resetPassword() })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.resetFor.set(null); this.resetPassword.set('');
          this.done(`Password reset for ${username}; their sessions were signed out`);
          this.focusAfterRender(this.resetButtonId(username));
        },
        error: e => this.fail(e),
      });
  }

  askDelete(username: string) {
    const target = this.findUser(username);
    if (!target || !this.canDelete(target) || username === this.me()) return;
    this.resetFor.set(null);
    this.resetPassword.set('');
    this.pendingDelete.set(username);
    this.focusAfterRender('cancel-delete');  // the safe choice gets focus first
  }

  confirmDelete() {
    const username = this.pendingDelete();
    const target = username ? this.findUser(username) : undefined;
    if (!username || !target || !this.canDelete(target) || username === this.me()) return;
    this.store.deleteUser(username)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.users.update(list => list.filter(u => u.username !== username));
          this.pendingDelete.set(null);
          this.done(`Deleted ${username}. Their open incidents are now unassigned.`);
          this.focusAfterRender('accounts-title');  // the row and its buttons are gone
        },
        error: e => { this.pendingDelete.set(null); this.fail(e); },
      });
  }

  /** Close an inline reset or delete confirmation; focus returns to the button that opened it. */
  cancel() {
    const reset = this.resetFor();
    const del = this.pendingDelete();
    this.pendingDelete.set(null);
    this.resetFor.set(null);
    this.resetPassword.set('');
    if (reset) this.focusAfterRender(this.resetButtonId(reset));
    else if (del) this.focusAfterRender(this.deleteButtonId(del));
  }

  readonly resetButtonId  = (username: string) => `reset-btn-${username}`;
  readonly deleteButtonId = (username: string) => `delete-btn-${username}`;

  /** Move focus once the next render has put the element in the DOM. */
  private focusAfterRender(id: string) {
    afterNextRender(() => document.getElementById(id)?.focus(), { injector: this.injector });
  }

  private findUser(username: string): UserSummary | undefined {
    return this.users().find(u => u.username === username);
  }

  private done(message: string) {
    this.error.set(null);
    this.notice.set(message);
  }

  private fail(e: HttpErrorResponse) {
    this.notice.set(null);
    const detail = e.error?.detail;
    this.error.set(typeof detail === 'string' ? detail : 'The request failed');
  }
}
