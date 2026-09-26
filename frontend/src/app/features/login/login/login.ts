import { Component, signal, inject, ChangeDetectionStrategy } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { AuthService } from '../../../core/services/auth';
import { DemoModeService } from '../../../core/services/demo-mode.service';

/** Public demo accounts (seeded only in demo mode; shown on this page). */
export const DEMO_ACCOUNTS = [
  { label: 'Try as Admin',   username: 'admin', password: 'admin-demo' },
  { label: 'Try as Analyst', username: 'alice', password: 'alice-demo' },
] as const;

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './login.html',
  styleUrl: './login.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Login {
  // ── public signals ────────────────────────────────────────────
  username       = signal('');
  password       = signal('');
  loading        = signal(false);
  error          = signal<string | null>(null);
  slowConnection = signal(false);

  // ── private injections ────────────────────────────────────────
  private readonly auth   = inject(AuthService);
  private readonly router = inject(Router);
  readonly demo           = inject(DemoModeService);
  readonly demoAccounts   = DEMO_ACCOUNTS;
  private slowTimer: ReturnType<typeof setTimeout> | null = null;
  private startupTimer: ReturnType<typeof setTimeout> | null = null;

  constructor() {
    this.demo.load();  // demo buttons only make sense when the server is in demo mode
    // Show "Server is waking up" if the server is slow to respond on cold start
    this.startupTimer = setTimeout(() => this.slowConnection.set(true), 3000);
    this.auth.ping().subscribe(() => {
      if (this.startupTimer) { clearTimeout(this.startupTimer); this.startupTimer = null; }
      this.slowConnection.set(false);
    });
  }

  // ── public methods ────────────────────────────────────────────
  submit() {
    if (!this.username() || !this.password()) return;
    this.loading.set(true);
    this.error.set(null);
    this.slowConnection.set(false);

    this.slowTimer = setTimeout(() => this.slowConnection.set(true), 3000);

    const clearTimer = () => {
      if (this.slowTimer) { clearTimeout(this.slowTimer); this.slowTimer = null; }
      this.slowConnection.set(false);
    };

    this.auth.login(this.username(), this.password()).subscribe({
      next:  () => { clearTimer(); this.router.navigate(['/dashboard']); },
      error: (err: HttpErrorResponse) => {
        clearTimer();
        this.error.set(err.status === 429 ? 'Too many attempts, try again in a minute' : 'Invalid credentials');
        this.loading.set(false);
      },
    });
  }

  demoLogin(account: (typeof DEMO_ACCOUNTS)[number]) {
    this.username.set(account.username);
    this.password.set(account.password);
    this.submit();
  }
}
