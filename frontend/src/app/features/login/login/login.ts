import { Component, signal, inject, ChangeDetectionStrategy } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../../../core/services/auth';

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
  private slowTimer: ReturnType<typeof setTimeout> | null = null;

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
      error: () => { clearTimer(); this.error.set('Invalid credentials'); this.loading.set(false); },
    });
  }

  demoLogin() {
    this.username.set('analyst');
    this.password.set('signalforge');
    this.submit();
  }
}
