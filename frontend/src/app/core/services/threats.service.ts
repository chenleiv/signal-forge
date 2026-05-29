import { Injectable, inject, signal } from '@angular/core';
import { ThreatStoreService } from './threat-store.service';
import { ThreatEvent } from '../../shared/models/threat.models';
import { NotificationService } from './notification.service';

@Injectable({ providedIn: 'root' })
export class ThreatsService {
  private socket!: WebSocket;
  private statsInterval!: ReturnType<typeof setInterval>;
  private store = inject(ThreatStoreService);
  private destroyed = false;
  private notif = inject(NotificationService);

  readonly status = signal<'connected' | 'reconnecting' | 'disconnected'>('disconnected');

  connect() {
    this.destroyed = false;
    this.status.set('reconnecting');
    this.notif.requestPermission();
    this.socket = new WebSocket('ws://127.0.0.1:8000/ws/threats');

    this.socket.onopen = () => {
      this.status.set('connected');
    };

    this.socket.onmessage = (event) => {
      const data: ThreatEvent = JSON.parse(event.data);
      this.store.addEvent(data);
      if (data.threat_level === 'critical' && data.score >= 95) {
        this.notif.notify(
          `⚠ Critical Threat Detected`,
          `${data.attack_type} from ${data.ip} — Score: ${data.score}`,
        );
      }
    };

    this.socket.onclose = () => {
      this.status.set('reconnecting');
      if (!this.destroyed) {
        setTimeout(() => this.connect(), 3000);
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
