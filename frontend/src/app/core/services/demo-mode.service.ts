import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';

const NOTICE_MS = 4000;

/**
 * UI side of read-only demo mode. The server is the security boundary
 * (it rejects writes with 403); this service only explains that to the user.
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

  showBlocked(): void {
    this.enabled.set(true);
    this.notice.set('This action is disabled in the read-only demo.');
    if (this.noticeTimer) clearTimeout(this.noticeTimer);
    this.noticeTimer = setTimeout(() => this.notice.set(null), NOTICE_MS);
  }

  dismiss(): void {
    if (this.noticeTimer) clearTimeout(this.noticeTimer);
    this.notice.set(null);
  }
}
