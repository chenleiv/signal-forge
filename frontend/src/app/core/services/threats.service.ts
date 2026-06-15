import { Injectable, inject, signal } from '@angular/core';
import { Subscription, timer, switchMap, catchError, EMPTY } from 'rxjs';
import { ThreatStoreService } from './threat-store.service';
import { ThreatEvent } from '../../shared/models/threat.models';
import { SettingsService } from './settings.service';
import { AuthService } from './auth';

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

  readonly status         = signal<'connected' | 'reconnecting' | 'disconnected'>('disconnected');
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

    this.socket.onclose = () => {
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

  disconnect() {
    this.destroyed = true;
    this.status.set('disconnected');
    this.socket?.close();
    this.statsSub?.unsubscribe();
    this.alertSub?.unsubscribe();
  }
}
