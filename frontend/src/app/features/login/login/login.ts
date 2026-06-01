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
  username = signal('');
  password = signal('');
  loading  = signal(false);
  error    = signal<string | null>(null);

  // ── private injections ────────────────────────────────────────
  private readonly auth   = inject(AuthService);
  private readonly router = inject(Router);

  // ── public methods ────────────────────────────────────────────
  submit() {
    if (!this.username() || !this.password()) return;
    this.loading.set(true);
    this.error.set(null);
    this.auth.login(this.username(), this.password()).subscribe({
      next:  () => this.router.navigate(['/dashboard']),
      error: () => { this.error.set('Invalid credentials'); this.loading.set(false); },
    });
  }

  demoLogin() {
    this.username.set('analyst');
    this.password.set('threatwatcher');
    this.submit();
  }
}
