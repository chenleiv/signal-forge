import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { Observable, Subject, of, throwError } from 'rxjs';

import {
  MAX_RECONNECT_MS, STATS_INTERVAL_MS, STATS_PAUSE_MS, ThreatsService,
} from './threats.service';
import { AuthService } from './auth';
import { SettingsService } from './settings.service';
import { ThreatStoreService } from './threat-store.service';

/** Records every socket the service opens; tests drive open/close by hand. */
class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: ((e: CloseEvent) => void) | null = null;

  constructor(readonly url: string) { FakeWebSocket.instances.push(this); }

  close() { /* client-side close: the tests fire onclose themselves */ }
  open() { this.onopen?.(); }
  serverClose(code: number) { this.onclose?.({ code } as CloseEvent); }
}

const RECONNECT_DELAY_S = 3;

describe('ThreatsService reconnect and stats rate limit', () => {
  let service: ThreatsService;
  let tickets: Subject<string>[];
  let statsCalls: number;
  let alertCalls: number;
  let statsReply: () => Observable<unknown>;
  const stats = signal<unknown>(null);

  const lastSocket = () => FakeWebSocket.instances[FakeWebSocket.instances.length - 1];
  const grantTicket = () => { const t = tickets[tickets.length - 1]; t.next('ticket'); t.complete(); };
  const failTicket = (status: number) => tickets[tickets.length - 1].error({ status });

  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal('WebSocket', FakeWebSocket);
    FakeWebSocket.instances = [];
    tickets = [];
    statsCalls = 0;
    alertCalls = 0;
    statsReply = () => of({ top_ips: [] });
    stats.set(null);

    TestBed.configureTestingModule({
      providers: [
        { provide: AuthService, useValue: {
          getWsTicket: (): Observable<string> => { const t = new Subject<string>(); tickets.push(t); return t; },
        } },
        { provide: SettingsService, useValue: {
          settings: signal({ wsUrl: 'ws://test/ws/threats', reconnectDelay: RECONNECT_DELAY_S }),
        } },
        { provide: ThreatStoreService, useValue: {
          addEvent: () => undefined,
          refreshStats: () => { statsCalls++; return statsReply(); },
          fetchAlerts: () => { alertCalls++; return of([]); },
          stats,
          alerts: signal([]),
        } },
      ],
    });
    service = TestBed.inject(ThreatsService);
  });

  afterEach(() => {
    service.disconnect();
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  const connectAndOpen = () => {
    service.connect();
    grantTicket();
    lastSocket().open();
    expect(service.status()).toBe('connected');
  };

  describe('a failed ticket request', () => {
    it('shows signed out and stops on a 401', () => {
      service.connect();
      failTicket(401);
      expect(service.status()).toBe('signed-out');
      vi.advanceTimersByTime(MAX_RECONNECT_MS * 4);
      expect(tickets).toHaveLength(1);
    });

    it('shows signed out and stops on a 403', () => {
      service.connect();
      failTicket(403);
      expect(service.status()).toBe('signed-out');
      vi.advanceTimersByTime(MAX_RECONNECT_MS * 4);
      expect(tickets).toHaveLength(1);
    });

    it('retries while the server is unreachable, with a doubling delay capped at the maximum', () => {
      service.connect();
      const base = RECONNECT_DELAY_S * 1000;
      const expected = [base, base * 2, base * 4, base * 8, MAX_RECONNECT_MS, MAX_RECONNECT_MS];
      for (const delay of expected) {
        const before = tickets.length;
        failTicket(502);
        expect(service.status()).toBe('reconnecting');
        vi.advanceTimersByTime(delay - 1);
        expect(tickets).toHaveLength(before);       // not yet
        vi.advanceTimersByTime(1);
        expect(tickets).toHaveLength(before + 1);   // retried
      }
      failTicket(0);                                  // network error: retried too
      vi.advanceTimersByTime(MAX_RECONNECT_MS);
      expect(tickets).toHaveLength(expected.length + 2);
    });
  });

  it('after a backend restart: returns to connected, resumes polling and resets the backoff', () => {
    connectAndOpen();
    lastSocket().serverClose(1012);                  // server restarting

    // First reconnect: the server is still down.
    vi.advanceTimersByTime(RECONNECT_DELAY_S * 1000);
    failTicket(503);
    // Second: the server is back.
    vi.advanceTimersByTime(RECONNECT_DELAY_S * 2000);
    const stats0 = statsCalls;
    const alerts0 = alertCalls;
    grantTicket();
    lastSocket().open();
    expect(service.status()).toBe('connected');

    vi.advanceTimersByTime(STATS_INTERVAL_MS * 3);
    expect(statsCalls).toBeGreaterThan(stats0);      // stats polling resumed
    expect(alertCalls).toBeGreaterThan(alerts0);     // alerts polling resumed

    // The backoff was reset by the open: the next drop waits the base delay.
    const before = tickets.length;
    lastSocket().serverClose(1006);
    vi.advanceTimersByTime(RECONNECT_DELAY_S * 1000);
    expect(tickets).toHaveLength(before + 1);
  });

  it('a replaced socket does not schedule a reconnect when it closes later', () => {
    connectAndOpen();
    const old = lastSocket();
    service.connect();                                // e.g. a settings change
    expect(old.onclose).toBeNull();
    grantTicket();
    lastSocket().open();
    vi.advanceTimersByTime(MAX_RECONNECT_MS * 2);
    expect(tickets).toHaveLength(2);
  });

  describe('a 429 on /api/stats', () => {
    const limited = () => throwError(() => new HttpErrorResponse({ status: 429 }));

    it('sets statsLimited, pauses polling for one window, then resumes and clears it', () => {
      statsReply = limited;
      connectAndOpen();
      vi.advanceTimersByTime(0);                      // the first poll
      expect(statsCalls).toBe(1);
      expect(service.statsLimited()).toBe(true);

      vi.advanceTimersByTime(STATS_PAUSE_MS - STATS_INTERVAL_MS);
      expect(statsCalls).toBe(1);                     // no polls into the limit

      statsReply = () => of({ top_ips: [] });
      vi.advanceTimersByTime(STATS_INTERVAL_MS);      // the window has passed
      expect(statsCalls).toBe(2);
      expect(service.statsLimited()).toBe(false);
      expect(stats()).not.toBeNull();
    });

    it('keeps other errors silent and keeps polling', () => {
      statsReply = () => throwError(() => new HttpErrorResponse({ status: 500 }));
      connectAndOpen();
      vi.advanceTimersByTime(STATS_INTERVAL_MS * 2);
      expect(statsCalls).toBe(3);
      expect(service.statsLimited()).toBe(false);
    });
  });
});
