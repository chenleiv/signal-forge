import {
  Component, computed, inject, signal, ChangeDetectionStrategy, DestroyRef, ElementRef, Injector,
  afterNextRender, viewChild,
} from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { SettingsService, AppSettings } from '../../core/services/settings.service';
import { AuthService } from '../../core/services/auth';
import { ThemeService } from '../../core/services/theme';
import { DemoModeService } from '../../core/services/demo-mode.service';

const MIN_PASSWORD_BYTES = 12;
const MAX_PASSWORD_BYTES = 72;   // bcrypt limit; same rule as the server

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [],
  templateUrl: './settings.html',
  styleUrl: './settings.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Settings {
  private svc = inject(SettingsService);
  readonly auth = inject(AuthService);
  readonly themeService = inject(ThemeService);
  private readonly demo = inject(DemoModeService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly injector = inject(Injector);

  form = signal<AppSettings>({ ...this.svc.settings() });

  saved = signal(false);

  save() {
    this.svc.save(this.form());
    this.saved.set(true);
    setTimeout(() => this.saved.set(false), 2000);
  }

  reset() {
    this.svc.reset();
    this.form.set({ ...this.svc.settings() });
  }

  logout() {
    this.auth.logout();
  }

  // ── Change own password ──────────────────────────────────────
  // The demo accounts are shared and their passwords are public: changing
  // them is blocked (the server refuses it too).
  readonly pwLocked   = computed(() => this.demo.enabled());
  readonly currentPw  = signal('');
  readonly newPw      = signal('');
  readonly confirmPw  = signal('');
  readonly pwBusy     = signal(false);
  readonly pwError    = signal<string | null>(null);
  readonly pwNotice   = signal<string | null>(null);

  // Collapsed by default. The native details element owns the open state: pwOpen only
  // mirrors it (toggle event), and code changes it through setPwOpen, never by binding.
  readonly pwOpen = signal(false);
  private readonly pwDetails = viewChild.required<ElementRef<HTMLDetailsElement>>('pwDetails');
  private readonly pwSummary = viewChild.required<ElementRef<HTMLElement>>('pwSummary');
  private readonly currentPwInput = viewChild.required<ElementRef<HTMLInputElement>>('currentPwInput');

  /** Opens or closes the details element; onPwToggle then runs from its toggle event. */
  setPwOpen(open: boolean) {
    this.pwDetails().nativeElement.open = open;
    this.pwOpen.set(open);
  }

  onPwToggle() {
    const open = this.pwDetails().nativeElement.open;
    this.pwOpen.set(open);
    if (open) {
      this.pwNotice.set(null);
      if (!this.pwLocked()) this.currentPwInput().nativeElement.focus();
    } else {
      // Closing discards what was typed and any error; a success notice stays visible.
      this.currentPw.set(''); this.newPw.set(''); this.confirmPw.set('');
      this.pwError.set(null);
    }
  }

  /** A client-side check for quick feedback; the server re-checks everything. */
  readonly pwProblem = computed((): string | null => {
    const next = this.newPw();
    if (!this.currentPw() || !next) return null;
    const bytes = new TextEncoder().encode(next).length;
    if (bytes < MIN_PASSWORD_BYTES || bytes > MAX_PASSWORD_BYTES) {
      return `The new password must be ${MIN_PASSWORD_BYTES}-${MAX_PASSWORD_BYTES} characters`;
    }
    if (next === this.currentPw()) return 'The new password must be different from the current one';
    if (this.confirmPw() && next !== this.confirmPw()) return 'The new passwords do not match';
    return null;
  });

  readonly canSubmitPw = computed(() =>
    !this.pwLocked() && !this.pwBusy() && !!this.currentPw() && !!this.newPw()
    && this.newPw() === this.confirmPw() && this.pwProblem() === null);

  changePassword() {
    if (!this.canSubmitPw()) return;   // re-checked here, not only on the button
    this.pwBusy.set(true);
    this.pwError.set(null);
    this.pwNotice.set(null);
    this.auth.changePassword(this.currentPw(), this.newPw())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.pwBusy.set(false);
          this.currentPw.set(''); this.newPw.set(''); this.confirmPw.set('');
          this.pwNotice.set('Password changed. Your other sessions were signed out.');
          // Close the form; the submit button is hidden with it, so focus goes back to the summary.
          this.setPwOpen(false);
          afterNextRender(() => this.pwSummary().nativeElement.focus(), { injector: this.injector });
        },
        error: (e: HttpErrorResponse) => {
          this.pwBusy.set(false);
          const detail = e.error?.detail;
          this.pwError.set(
            e.status === 429 ? 'Too many attempts. Try again in a minute.'
            : typeof detail === 'string' ? detail
            : 'The password could not be changed',
          );
        },
      });
  }
}
