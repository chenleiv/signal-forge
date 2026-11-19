import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { Observable, Subject, of } from 'rxjs';

import { MAX_RECONNECT_MS, ThreatsService } from './threats.service';
import { AuthService } from './auth';
import { SettingsService } from './settings.service';
import { ThreatStoreService } from './threat-store.service';

/**
 * Guard for the WebSocket limits on the server: a refused handshake (cap
 * reached, HTTP 429, which the browser reports as 1006), an oversized first
 * frame (1009) and a frame sent after ready (1008) must all reconnect with
 * the doubling backoff: never in a tight loop, never "signed out".
 */
class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: ((e: CloseEvent) => void) | null = null;

  constructor(readonly url: string) { FakeWebSocket.instances.push(this); }

  send() { /* the ticket; not inspected here */ }
  close() { /* client-side close: the tests fire onclose themselves */ }
  /** Opens and authenticates: the server's ready frame follows the open. */
  open() { this.onopen?.(); this.onmessage?.({ data: JSON.stringify({ type: 'ready' }) } as MessageEvent); }
  serverClose(code: number) { this.onclose?.({ code } as CloseEvent); }
}

const RECONNECT_DELAY_S = 3;
const BASE_MS = RECONNECT_DELAY_S * 1000;

describe('ThreatsService close codes from the WebSocket limits', () => {
  let service: ThreatsService;
  let tickets: Subject<string>[];

  const lastSocket = () => FakeWebSocket.instances[FakeWebSocket.instances.length - 1];
  const grantTicket = () => { const t = tickets[tickets.length - 1]; t.next('ticket'); t.complete(); };

  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal('WebSocket', FakeWebSocket);
    FakeWebSocket.instances = [];
    tickets = [];

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
          refreshStats: () => of({ top_ips: [] }),
          fetchAlerts: () => of([]),
          stats: signal(null),
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

  /** Waits `delay` and checks that exactly one new ticket request follows it, not earlier. */
  const expectRetryAfter = (delay: number) => {
    const before = tickets.length;
    vi.advanceTimersByTime(delay - 1);
    expect(tickets).toHaveLength(before);
    vi.advanceTimersByTime(1);
    expect(tickets).toHaveLength(before + 1);
  };

  for (const [name, code] of [['a refused handshake (cap reached)', 1006], ['a first frame over the size limit', 1009]] as const) {
    it(`backs off with a doubling delay after ${name} before ready (${code})`, () => {
      service.connect();
      for (const delay of [BASE_MS, BASE_MS * 2, BASE_MS * 4, BASE_MS * 8, MAX_RECONNECT_MS]) {
        grantTicket();
        lastSocket().serverClose(code);      // never reached ready
        expect(service.status()).toBe('reconnecting');
        expectRetryAfter(delay);
      }
    });
  }

  it('reconnects after the base delay, not at once, when the stream ends with 1008 after ready', () => {
    service.connect();
    grantTicket();
    lastSocket().open();
    expect(service.status()).toBe('connected');

    lastSocket().serverClose(1008);
    expect(service.status()).toBe('reconnecting');
    expectRetryAfter(BASE_MS);
  });
});
