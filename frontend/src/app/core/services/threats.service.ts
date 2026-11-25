import { Injectable, inject, signal } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { Subscription, timer, switchMap, catchError, filter, EMPTY } from 'rxjs';
import { ThreatStoreService } from './threat-store.service';
import { ThreatEvent } from '../../shared/models/threat.models';
import { SettingsService } from './settings.service';
import { AuthService } from './auth';

/** Close code the server sends when the stream's session has ended. */
export const WS_SESSION_ENDED = 4001;

export type StreamStatus = 'connected' | 'reconnecting' | 'disconnected' | 'signed-out';

/** Stats polling interval. */
export const STATS_INTERVAL_MS = 5000;
/** Alerts polling interval. */
export const ALERTS_INTERVAL_MS = 15_000;
/** Pause after a 429 on /api/stats or /api/alerts when the response has no
 *  usable Retry-After: the server limits are fixed one-minute windows per IP,
 *  so wait one full window. */
export const STATS_PAUSE_MS = 60_000;
/** Longest pause taken from a Retry-After header. */
export const MAX_PAUSE_MS = 3_600_000;
/** Upper bound for the reconnect backoff. */
export const MAX_RECONNECT_MS = 30_000;

/** The first message on a new socket: the ticket from /auth/ws-ticket. */
interface WsAuthMessage { type: 'auth'; ticket: string }

/** The server's answer to a valid ticket; events follow it. */
function isReady(data: unknown): boolean {
  return typeof data === 'object' && data !== null && (data as { type?: unknown }).type === 'ready';
}

/** HTTP status of an error, if it has one. */
function statusOf(err: unknown): number | undefined {
  const status = (err as { status?: unknown } | null)?.status;
  return typeof status === 'number' ? status : undefined;
}

/** The wait a 429 asks for, from its Retry-After header (whole seconds),
 *  capped at MAX_PAUSE_MS; `fallbackMs` when the header is missing or not a
 *  positive integer. */
export function retryAfterMs(err: unknown, fallbackMs: number): number {
  const headers = err instanceof HttpErrorResponse ? err.headers : undefined;
  const value = headers?.get('Retry-After')?.trim() ?? '';
  const seconds = /^\d+$/.test(value) ? Number(value) : 0;
  return seconds > 0 ? Math.min(seconds * 1000, MAX_PAUSE_MS) : fallbackMs;
}

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
  // Set after a 4001 until the server accepts a ticket again: a second 4001
  // in a row means signed out, with no further ticket request.
  private sessionChecked = false;
  // Reconnect backoff: the delay doubles per failed attempt, capped at
  // MAX_RECONNECT_MS, and resets when the server accepts a ticket.
  private reconnectAttempt = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  // Stats and alerts polls are skipped until these times after a 429.
  private statsPausedUntil = 0;
  private alertsPausedUntil = 0;

  readonly status         = signal<StreamStatus>('disconnected');
  readonly slowConnection = signal(false);
  /** True after a 429 on /api/stats, until the next successful poll. */
  readonly statsLimited   = signal(false);

  private startSlowTimer() {
    if (this.slowTimer) return;
    this.slowTimer = setTimeout(() => this.slowConnection.set(true), 5000);
  }

  private clearSlowTimer() {
    if (this.slowTimer) { clearTimeout(this.slowTimer); this.slowTimer = null; }
    this.slowConnection.set(false);
  }

  connect() {
    this.clearReconnectTimer();
    this.statsSub?.unsubscribe();
    this.alertSub?.unsubscribe();
    if (this.socket) {
      // A replaced socket must not schedule a reconnect of its own when its
      // close event arrives later.
      this.socket.onclose = null;
      this.socket.onerror = null;
      this.socket.close();
    }
    this.destroyed = false;
    this.status.set('reconnecting');
    this.startSlowTimer();

    this.authService.getWsTicket().subscribe({
      next: ticket => { if (!this.destroyed) this.openSocket(ticket); },
      error: (err: unknown) => {
        const status = statusOf(err);
        if (status === 401 || status === 403) {
          // The session is gone (e.g. the server restarted without a
          // database): retrying cannot help.
          this.clearSlowTimer();
          this.status.set('signed-out');
          return;
        }
        // The server is unreachable or still starting: try again.
        this.scheduleReconnect();
      },
    });
  }

  private scheduleReconnect() {
    if (this.destroyed) return;
    this.status.set('reconnecting');
    this.clearReconnectTimer();
    const base = this.settingsService.settings().reconnectDelay * 1000;
    const delay = Math.min(base * 2 ** this.reconnectAttempt, MAX_RECONNECT_MS);
    this.reconnectAttempt++;
    this.reconnectTimer = setTimeout(() => { this.reconnectTimer = null; this.connect(); }, delay);
  }

  private clearReconnectTimer() {
    if (this.reconnectTimer) { clearTimeout(this.reconnectTimer); this.reconnectTimer = null; }
  }

  private openSocket(ticket: string) {
    // The ticket goes in the first message, never in the URL, so it cannot
    // end up in server or proxy access logs.
    this.socket = new WebSocket(this.settingsService.settings().wsUrl);

    this.socket.onopen = () => {
      const auth: WsAuthMessage = { type: 'auth', ticket };
      this.socket.send(JSON.stringify(auth));
    };

    this.socket.onmessage = (event) => {
      let data: unknown;
      try { data = JSON.parse(event.data); } catch { return; /* ignore non-JSON frames */ }
      if (isReady(data)) {
        // Connected only once the server accepted the ticket: an open socket
        // that is then closed with 4001 must not reset the session check or
        // the backoff, or it would reconnect in a loop.
        this.clearSlowTimer();
        this.sessionChecked = false;
        this.reconnectAttempt = 0;
        this.status.set('connected');
        return;
      }
      this.store.addEvent(data as ThreatEvent);
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
      this.scheduleReconnect();
    };

    // Polling (re)starts with every socket, so it resumes after a reconnect.
    this.statsSub = timer(0, STATS_INTERVAL_MS).pipe(
      filter(() => Date.now() >= this.statsPausedUntil),
      switchMap(() => this.store.refreshStats().pipe(catchError((err: unknown) => {
        if (statusOf(err) === 429) {
          // Rate limited (often many users behind one IP): say so and wait
          // out the window instead of polling into the limit.
          this.statsPausedUntil = Date.now() + retryAfterMs(err, STATS_PAUSE_MS);
          this.statsLimited.set(true);
        }
        return EMPTY;
      }))),
    ).subscribe((s) => { this.statsLimited.set(false); this.store.stats.set(s); });

    this.alertSub = timer(0, ALERTS_INTERVAL_MS).pipe(
      filter(() => Date.now() >= this.alertsPausedUntil),
      switchMap(() => this.store.fetchAlerts().pipe(catchError((err: unknown) => {
        // Rate limited: wait out the window; the list keeps its last value.
        if (statusOf(err) === 429) this.alertsPausedUntil = Date.now() + retryAfterMs(err, STATS_PAUSE_MS);
        return EMPTY;
      }))),
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
    this.clearReconnectTimer();
    this.status.set('disconnected');
    this.socket?.close();
    this.statsSub?.unsubscribe();
    this.alertSub?.unsubscribe();
  }
}
