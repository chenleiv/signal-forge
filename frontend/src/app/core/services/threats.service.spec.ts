import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { EMPTY, Observable, Subject } from 'rxjs';

import { ThreatsService, WS_SESSION_ENDED } from './threats.service';
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

describe('ThreatsService close handling', () => {
  let service: ThreatsService;
  let tickets: Subject<string>[];

  const lastSocket = () => FakeWebSocket.instances[FakeWebSocket.instances.length - 1];

  /** Answer the newest pending ticket request. */
  const grantTicket = () => { const t = tickets[tickets.length - 1]; t.next('ticket'); t.complete(); };
  const refuseTicket = () => tickets[tickets.length - 1].error({ status: 401 });

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
    lastSocket().open();
    expect(service.status()).toBe('connected');
  });

  afterEach(() => {
    service.disconnect();
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it('shows signed out and stops when the session has ended', () => {
    lastSocket().serverClose(WS_SESSION_ENDED);
    expect(tickets).toHaveLength(2);           // exactly one check
    refuseTicket();

    expect(service.status()).toBe('signed-out');
    vi.advanceTimersByTime(RECONNECT_DELAY_S * 1000 * 10);
    expect(tickets).toHaveLength(2);           // no retry
    expect(FakeWebSocket.instances).toHaveLength(1);
  });

  it('reconnects at once when the session is still valid (own password change)', () => {
    lastSocket().serverClose(WS_SESSION_ENDED);
    grantTicket();

    expect(FakeWebSocket.instances).toHaveLength(2);
    lastSocket().open();
    expect(service.status()).toBe('connected');
  });

  it('does not check twice in a row: a second 4001 before any open is signed out', () => {
    lastSocket().serverClose(WS_SESSION_ENDED);
    grantTicket();
    lastSocket().serverClose(WS_SESSION_ENDED);  // the new socket never opened

    expect(service.status()).toBe('signed-out');
    expect(tickets).toHaveLength(2);
    vi.advanceTimersByTime(RECONNECT_DELAY_S * 1000 * 10);
    expect(tickets).toHaveLength(2);
  });

  it('keeps reconnecting after the delay for any other close code', () => {
    lastSocket().serverClose(1006);

    expect(service.status()).toBe('reconnecting');
    expect(tickets).toHaveLength(1);
    vi.advanceTimersByTime(RECONNECT_DELAY_S * 1000);
    expect(tickets).toHaveLength(2);
  });
});
