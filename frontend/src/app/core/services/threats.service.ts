import { Injectable, inject, signal } from '@angular/core';
import { ThreatStoreService } from './threat-store.service';
import { ThreatEvent } from '../../shared/models/threat.models';
import { SettingsService } from './settings.service';

@Injectable({ providedIn: 'root' })
export class ThreatsService {
  private socket!: WebSocket;
  private statsInterval!: ReturnType<typeof setInterval>;
  private store = inject(ThreatStoreService);
  private settingsService = inject(SettingsService);

  private destroyed = false;

  readonly status = signal<'connected' | 'reconnecting' | 'disconnected'>('disconnected');

  connect() {
    this.destroyed = false;
    this.status.set('reconnecting');
    this.socket = new WebSocket(this.settingsService.settings().wsUrl);

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

    this.store.refreshStats();
    this.statsInterval = setInterval(() => this.store.refreshStats(), 5000);
  }

  disconnect() {
    this.destroyed = true;
    this.status.set('disconnected');
    this.socket?.close();
    clearInterval(this.statsInterval);
  }
}
