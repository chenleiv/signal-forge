import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { EMPTY, Observable, Subject } from 'rxjs';

import { ThreatsService, WS_SESSION_ENDED } from './threats.service';
import { AuthService } from './auth';
import { SettingsService } from './settings.service';
import { ThreatStoreService } from './threat-store.service';

/** Close code the server sends when no ticket arrives in time. */
const WS_AUTH_TIMEOUT = 4408;
const RECONNECT_DELAY_S = 3;
const WS_URL = 'ws://test/ws/threats';
const TICKET = 'secret-ticket';

/** A socket the test drives by hand; open() does not authenticate. */
class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: ((e: CloseEvent) => void) | null = null;
  sent: string[] = [];

  constructor(readonly url: string) { FakeWebSocket.instances.push(this); }

  send(data: string) { this.sent.push(data); }
  close() { /* client-side close: the tests fire onclose themselves */ }
  open() { this.onopen?.(); }
  receive(data: unknown) { this.onmessage?.({ data: JSON.stringify(data) } as MessageEvent); }
  serverClose(code: number) { this.onclose?.({ code } as CloseEvent); }
}

describe('ThreatsService ticket as the first message', () => {
  let service: ThreatsService;
  let tickets: Subject<string>[];
  let events: unknown[];

  const lastSocket = () => FakeWebSocket.instances[FakeWebSocket.instances.length - 1];
  const grantTicket = () => { const t = tickets[tickets.length - 1]; t.next(TICKET); t.complete(); };

  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal('WebSocket', FakeWebSocket);
    FakeWebSocket.instances = [];
    tickets = [];
    events = [];

    TestBed.configureTestingModule({
      providers: [
        { provide: AuthService, useValue: {
          getWsTicket: (): Observable<string> => { const t = new Subject<string>(); tickets.push(t); return t; },
        } },
        { provide: SettingsService, useValue: {
          settings: signal({ wsUrl: WS_URL, reconnectDelay: RECONNECT_DELAY_S }),
        } },
        { provide: ThreatStoreService, useValue: {
          addEvent: (e: unknown) => { events.push(e); },
          refreshStats: () => EMPTY,
          fetchAlerts: () => EMPTY,
          stats: signal(null),
          alerts: signal([]),
        } },
      ],
    });
    service = TestBed.inject(ThreatsService);
    service.connect();
    grantTicket();
  });

  afterEach(() => {
    service.disconnect();
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it('opens the socket without the ticket in the URL', () => {
    expect(lastSocket().url).toBe(WS_URL);
    expect(lastSocket().url).not.toContain(TICKET);
  });

  it('sends the ticket as the first message on open', () => {
    expect(lastSocket().sent).toEqual([]);
    lastSocket().open();
    expect(lastSocket().sent).toHaveLength(1);
    expect(JSON.parse(lastSocket().sent[0])).toEqual({ type: 'auth', ticket: TICKET });
  });

  it('stays reconnecting after open until the server sends ready', () => {
    lastSocket().open();
    expect(service.status()).toBe('reconnecting');
    lastSocket().receive({ type: 'ready' });
    expect(service.status()).toBe('connected');
  });

  it('does not pass the ready frame to the store, but passes events', () => {
    lastSocket().open();
    lastSocket().receive({ type: 'ready' });
    lastSocket().receive({ ip: '8.8.8.8', timestamp: 't' });
    expect(events).toEqual([{ ip: '8.8.8.8', timestamp: 't' }]);
  });

  it('a rejected ticket after open: one check, then signed out, no loop', () => {
    lastSocket().open();
    lastSocket().serverClose(WS_SESSION_ENDED);
    expect(tickets).toHaveLength(2);           // exactly one check
    grantTicket();
    lastSocket().open();                       // opens, but no ready
    lastSocket().serverClose(WS_SESSION_ENDED);

    expect(service.status()).toBe('signed-out');
    vi.advanceTimersByTime(RECONNECT_DELAY_S * 1000 * 10);
    expect(tickets).toHaveLength(2);
    expect(FakeWebSocket.instances).toHaveLength(2);
  });

  it('a timeout close reconnects with backoff, and an open without ready does not reset it', () => {
    const base = RECONNECT_DELAY_S * 1000;
    lastSocket().open();
    lastSocket().serverClose(WS_AUTH_TIMEOUT);
    expect(service.status()).toBe('reconnecting');
    vi.advanceTimersByTime(base);
    expect(tickets).toHaveLength(2);

    grantTicket();
    lastSocket().open();
    lastSocket().serverClose(WS_AUTH_TIMEOUT);
    vi.advanceTimersByTime(base);
    expect(tickets).toHaveLength(2);           // the delay doubled
    vi.advanceTimersByTime(base);
    expect(tickets).toHaveLength(3);
  });
});
