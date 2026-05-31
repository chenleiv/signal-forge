import { Injectable, inject, signal } from '@angular/core';
import { Subscription, timer, switchMap, catchError, EMPTY } from 'rxjs';
import { ThreatStoreService } from './threat-store.service';
import { ThreatEvent } from '../../shared/models/threat.models';
import { SettingsService } from './settings.service';

@Injectable({ providedIn: 'root' })
export class ThreatsService {
  private socket!: WebSocket;
  private statsSub?: Subscription;
  private store = inject(ThreatStoreService);
  private settingsService = inject(SettingsService);

  private destroyed = false;

  readonly status = signal<'connected' | 'reconnecting' | 'disconnected'>('disconnected');

  connect() {
    this.statsSub?.unsubscribe();
    this.socket?.close();
    this.destroyed = false;
    this.status.set('reconnecting');
    const token = localStorage.getItem('sf_token') ?? '';
    const wsUrl = `${this.settingsService.settings().wsUrl}?token=${token}`;
    this.socket = new WebSocket(wsUrl);

    this.socket.onopen = () => {
      this.status.set('connected');
    };

    this.socket.onmessage = (event) => {
      const data: ThreatEvent = JSON.parse(event.data);
      this.store.addEvent(data);
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
  }

  disconnect() {
    this.destroyed = true;
    this.status.set('disconnected');
    this.socket?.close();
    this.statsSub?.unsubscribe();
  }
}
