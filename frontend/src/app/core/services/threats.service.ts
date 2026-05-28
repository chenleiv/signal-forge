import { Injectable, inject } from '@angular/core';
import { ThreatStoreService } from './threat-store.service';
import { ThreatEvent } from '../../shared/models/threat.models';

@Injectable({ providedIn: 'root' })
export class ThreatsService {
  private socket!: WebSocket;
  private statsInterval!: ReturnType<typeof setInterval>;
  private store = inject(ThreatStoreService);

  connect() {
    this.socket = new WebSocket('ws://127.0.0.1:8000/ws/threats');

    this.socket.onmessage = (event) => {
      const data: ThreatEvent = JSON.parse(event.data);
      this.store.addEvent(data);
    };

    // Refresh aggregated stats every 5 seconds for charts
    this.store.refreshStats();
    this.statsInterval = setInterval(() => this.store.refreshStats(), 5000);
  }

  disconnect() {
    this.socket?.close();
    clearInterval(this.statsInterval);
  }
}
