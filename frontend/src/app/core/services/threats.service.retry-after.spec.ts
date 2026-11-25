import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { HttpErrorResponse, HttpHeaders } from '@angular/common/http';
import { Observable, Subject, of, throwError } from 'rxjs';

import {
  ALERTS_INTERVAL_MS, MAX_PAUSE_MS, STATS_INTERVAL_MS, STATS_PAUSE_MS, ThreatsService, retryAfterMs,
} from './threats.service';
import { AuthService } from './auth';
import { SettingsService } from './settings.service';
import { ThreatStoreService } from './threat-store.service';

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: ((e: CloseEvent) => void) | null = null;
  constructor(readonly url: string) { FakeWebSocket.instances.push(this); }
  send() { /* the ticket message; not checked here */ }
  close() { /* the tests never close */ }
  open() { this.onopen?.(); this.onmessage?.({ data: JSON.stringify({ type: 'ready' }) } as MessageEvent); }
}

const limited = (retryAfter?: string) => throwError(() => new HttpErrorResponse({
  status: 429,
  headers: retryAfter === undefined ? new HttpHeaders() : new HttpHeaders({ 'Retry-After': retryAfter }),
}));

describe('retryAfterMs', () => {
  const err = (value?: string) => new HttpErrorResponse({
    status: 429, headers: value === undefined ? new HttpHeaders() : new HttpHeaders({ 'Retry-After': value }),
  });

  it('uses whole seconds from the header', () => {
    expect(retryAfterMs(err('12'), 60_000)).toBe(12_000);
  });

  it('falls back when the header is missing, zero or not a whole number', () => {
    for (const value of [undefined, '', '0', '-5', '1.5', 'soon', 'Wed, 21 Oct 2026 07:28:00 GMT']) {
      expect(retryAfterMs(err(value), 60_000)).toBe(60_000);
    }
    expect(retryAfterMs({ status: 429 }, 60_000)).toBe(60_000);
  });

  it('caps a very long wait', () => {
    expect(retryAfterMs(err('999999'), 60_000)).toBe(MAX_PAUSE_MS);
  });
});

describe('ThreatsService polling after a 429', () => {
  let service: ThreatsService;
  let statsCalls: number;
  let alertCalls: number;
  let statsReply: () => Observable<unknown>;
  let alertsReply: () => Observable<unknown[]>;

  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal('WebSocket', FakeWebSocket);
    FakeWebSocket.instances = [];
    statsCalls = 0;
    alertCalls = 0;
    statsReply = () => of({ top_ips: [] });
    alertsReply = () => of([]);

    TestBed.configureTestingModule({
      providers: [
        { provide: AuthService, useValue: {
          getWsTicket: (): Observable<string> => { const t = new Subject<string>(); queueMicrotask(() => { t.next('ticket'); t.complete(); }); return t; },
        } },
        { provide: SettingsService, useValue: {
          settings: signal({ wsUrl: 'ws://test/ws/threats', reconnectDelay: 3 }),
        } },
        { provide: ThreatStoreService, useValue: {
          addEvent: () => undefined,
          refreshStats: () => { statsCalls++; return statsReply(); },
          fetchAlerts: () => { alertCalls++; return alertsReply(); },
          stats: signal<unknown>(null),
          alerts: signal<unknown[]>([]),
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

  const connectAndOpen = async () => {
    service.connect();
    await Promise.resolve();                       // the ticket arrives
    FakeWebSocket.instances[FakeWebSocket.instances.length - 1].open();
    vi.advanceTimersByTime(0);                     // the first polls
  };

  it('stats: pauses for the Retry-After seconds, then resumes', async () => {
    statsReply = () => limited('12');
    await connectAndOpen();
    expect(statsCalls).toBe(1);
    expect(service.statsLimited()).toBe(true);

    statsReply = () => of({ top_ips: [] });
    vi.advanceTimersByTime(10_000);
    expect(statsCalls).toBe(1);                    // still paused at 10 s
    vi.advanceTimersByTime(STATS_INTERVAL_MS);     // 15 s: past the 12 s wait
    expect(statsCalls).toBe(2);
    expect(service.statsLimited()).toBe(false);
  });

  it('alerts: pauses for the Retry-After seconds, then resumes', async () => {
    alertsReply = () => limited('40');
    await connectAndOpen();
    expect(alertCalls).toBe(1);

    alertsReply = () => of([]);
    vi.advanceTimersByTime(ALERTS_INTERVAL_MS * 2); // 30 s: inside the 40 s wait
    expect(alertCalls).toBe(1);
    vi.advanceTimersByTime(ALERTS_INTERVAL_MS);     // 45 s
    expect(alertCalls).toBe(2);
  });

  it('alerts: pauses one minute when the 429 has no Retry-After', async () => {
    alertsReply = () => limited();
    await connectAndOpen();
    alertsReply = () => of([]);
    vi.advanceTimersByTime(STATS_PAUSE_MS - ALERTS_INTERVAL_MS);
    expect(alertCalls).toBe(1);
    vi.advanceTimersByTime(ALERTS_INTERVAL_MS);
    expect(alertCalls).toBe(2);
  });

  it('alerts: other errors keep polling', async () => {
    alertsReply = () => throwError(() => new HttpErrorResponse({ status: 500 }));
    await connectAndOpen();
    vi.advanceTimersByTime(ALERTS_INTERVAL_MS * 2);
    expect(alertCalls).toBe(3);
  });
});
