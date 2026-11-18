import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { EMPTY, Observable, Subject } from 'rxjs';

import { ThreatsService, WS_SESSION_ENDED } from './threats.service';
import { AuthService } from './auth';
import { SettingsService } from './settings.service';
import { ThreatStoreService } from './threat-store.service';

// The server closes an open stream with 4001 when the 8-hour session token
// expires. The ticket check that follows gets a 401 (the cookie is expired),
// so the app must show signed out once and never reconnect.

const RECONNECT_DELAY_S = 3;
const WS_URL = 'ws://test/ws/threats';
const TICKET = 'secret-ticket';

/** A socket the test drives by hand. */
class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: ((e: CloseEvent) => void) | null = null;

  constructor(readonly url: string) { FakeWebSocket.instances.push(this); }

  send() { /* the ticket; not inspected here */ }
  close() { /* client-side close: the tests fire onclose themselves */ }
  open() { this.onopen?.(); }
  receive(data: unknown) { this.onmessage?.({ data: JSON.stringify(data) } as MessageEvent); }
  serverClose(code: number) { this.onclose?.({ code } as CloseEvent); }
}

describe('ThreatsService session expiry', () => {
  let service: ThreatsService;
  let tickets: Subject<string>[];
  let statsCalls: number;
  let alertCalls: number;

  const lastSocket = () => FakeWebSocket.instances[FakeWebSocket.instances.length - 1];
  const lastTicket = () => tickets[tickets.length - 1];

  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal('WebSocket', FakeWebSocket);
    FakeWebSocket.instances = [];
    tickets = [];
    statsCalls = 0;
    alertCalls = 0;

    TestBed.configureTestingModule({
      providers: [
        { provide: AuthService, useValue: {
          getWsTicket: (): Observable<string> => { const t = new Subject<string>(); tickets.push(t); return t; },
        } },
        { provide: SettingsService, useValue: {
          settings: signal({ wsUrl: WS_URL, reconnectDelay: RECONNECT_DELAY_S }),
        } },
        { provide: ThreatStoreService, useValue: {
          addEvent: () => undefined,
          refreshStats: () => { statsCalls++; return EMPTY; },
          fetchAlerts: () => { alertCalls++; return EMPTY; },
          stats: signal(null),
          alerts: signal([]),
        } },
      ],
    });
    service = TestBed.inject(ThreatsService);
    service.connect();
    lastTicket().next(TICKET);
    lastTicket().complete();
    lastSocket().open();
    lastSocket().receive({ type: 'ready' });
  });

  afterEach(() => {
    service.disconnect();
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it('a connected stream closed at expiry: one session check, then signed out, no loop', () => {
    expect(service.status()).toBe('connected');

    lastSocket().serverClose(WS_SESSION_ENDED);
    expect(tickets).toHaveLength(2);           // exactly one session check
    lastTicket().error({ status: 401 });       // the expired cookie
    expect(service.status()).toBe('signed-out');

    const stats = statsCalls;
    const alerts = alertCalls;
    vi.advanceTimersByTime(RECONNECT_DELAY_S * 1000 * 10);
    expect(tickets).toHaveLength(2);
    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(statsCalls).toBe(stats);            // polling stopped with the stream
    expect(alertCalls).toBe(alerts);
    expect(service.status()).toBe('signed-out');
  });
});
