import { Injectable, inject, signal } from '@angular/core';
import { Subscription, timer, switchMap, catchError, EMPTY } from 'rxjs';
import { ThreatStoreService } from './threat-store.service';
import { ThreatEvent } from '../../shared/models/threat.models';
import { SettingsService } from './settings.service';
import { AuthService } from './auth';

/** Close code the server sends when the stream's session has ended. */
export const WS_SESSION_ENDED = 4001;

export type StreamStatus = 'connected' | 'reconnecting' | 'disconnected' | 'signed-out';

@Injectable({ providedIn: 'root' })
export class ThreatsService {
  private socket!: WebSocket;
  private statsSub?: Subscription;
  private alertSub?: Subscription;
  private store         = inject(ThreatStoreService);
  private settingsService = inject(SettingsService);
  private authService   = inject(AuthService);

  private destroyed = false;
  private slowTimer: ReturnType<typeof setTimeout> | null = null;
  // Set after a 4001 until a socket opens again: a second 4001 in a row
  // means signed out, with no further ticket request.
  private sessionChecked = false;

  readonly status         = signal<StreamStatus>('disconnected');
  readonly slowConnection = signal(false);

  private startSlowTimer() {
    if (this.slowTimer) return;
    this.slowTimer = setTimeout(() => this.slowConnection.set(true), 5000);
  }

  private clearSlowTimer() {
    if (this.slowTimer) { clearTimeout(this.slowTimer); this.slowTimer = null; }
    this.slowConnection.set(false);
  }

  connect() {
    this.statsSub?.unsubscribe();
    this.alertSub?.unsubscribe();
    this.socket?.close();
    this.destroyed = false;
    this.status.set('reconnecting');
    this.startSlowTimer();

    this.authService.getWsTicket().subscribe({
      next: ticket => this.openSocket(ticket),
      error: () => { this.clearSlowTimer(); this.status.set('disconnected'); },
    });
  }

  private openSocket(ticket: string) {
    const wsUrl = `${this.settingsService.settings().wsUrl}?ticket=${ticket}`;
    this.socket = new WebSocket(wsUrl);

    this.socket.onopen = () => {
      this.clearSlowTimer();
      this.sessionChecked = false;
      this.status.set('connected');
    };

    this.socket.onmessage = (event) => {
      try {
        const data: ThreatEvent = JSON.parse(event.data);
        this.store.addEvent(data);
      } catch { /* ignore non-JSON frames */ }
    };

    this.socket.onerror = () => {
      this.status.set('reconnecting');
    };

    this.socket.onclose = (event: CloseEvent) => {
      if (event.code === WS_SESSION_ENDED && !this.destroyed) {
        this.onSessionEnded();
        return;
      }
      this.status.set('reconnecting');
      if (!this.destroyed) {
        setTimeout(() => this.connect(), this.settingsService.settings().reconnectDelay * 1000);
      }
    };

    this.statsSub = timer(0, 5000).pipe(
      switchMap(() => this.store.refreshStats().pipe(catchError(() => EMPTY))),
    ).subscribe((s) => this.store.stats.set(s));

    this.alertSub = timer(0, 15_000).pipe(
      switchMap(() => this.store.fetchAlerts().pipe(catchError(() => EMPTY))),
    ).subscribe(alerts => this.store.alerts.set(alerts));
  }

  /** The server ended the stream's session. One ticket request tells why:
   *  a valid session (e.g. this tab changed its own password, which rotates
   *  the session key) reconnects at once; otherwise the user is signed out
   *  and nothing retries. */
  private onSessionEnded() {
    this.statsSub?.unsubscribe();
    this.alertSub?.unsubscribe();
    if (this.sessionChecked) {
      this.status.set('signed-out');
      return;
    }
    this.sessionChecked = true;
    this.status.set('reconnecting');
    this.authService.getWsTicket().subscribe({
      next: ticket => { if (!this.destroyed) this.openSocket(ticket); },
      error: () => { this.clearSlowTimer(); this.status.set('signed-out'); },
    });
  }

  disconnect() {
    this.destroyed = true;
    this.status.set('disconnected');
    this.socket?.close();
    this.statsSub?.unsubscribe();
    this.alertSub?.unsubscribe();
  }
}
