import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';

const NOTICE_MS = 4000;

/**
 * UI side of demo mode. The server is the security boundary (it rejects
 * writes with 403); this service only tells the user what is happening.
 */
@Injectable({ providedIn: 'root' })
export class DemoModeService {
  private http = inject(HttpClient);
  private noticeTimer: ReturnType<typeof setTimeout> | null = null;

  readonly enabled = signal(false);
  readonly notice  = signal<string | null>(null);

  load(): void {
    this.http.get<{ demo_mode: boolean }>('/api/config').subscribe({
      next:  (cfg) => this.enabled.set(cfg.demo_mode),
      error: () => { /* banner is optional; the server still enforces */ },
    });
  }

  /** A write was simulated locally instead of being sent. */
  showSimulated(): void {
    this.show('Demo mode: change simulated in your browser, not saved.');
  }

  /** Fallback: the server rejected a write we did not simulate. */
  showBlocked(): void {
    this.enabled.set(true);
    this.show('This action is not available in the demo.');
  }

  /** The server denied an action for this user (403 with its reason). */
  showDenied(reason: string): void {
    this.show(reason);
  }

  private show(message: string): void {
    this.notice.set(message);
    if (this.noticeTimer) clearTimeout(this.noticeTimer);
    this.noticeTimer = setTimeout(() => this.notice.set(null), NOTICE_MS);
  }

  dismiss(): void {
    if (this.noticeTimer) clearTimeout(this.noticeTimer);
    this.notice.set(null);
  }
}
