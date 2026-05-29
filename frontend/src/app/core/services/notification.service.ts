import { Injectable } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class NotificationService {
  private lastNotif = 0;
  private readonly COOLDOWN_MS = 30_000;

  requestPermission() {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }
  }

  notify(title: string, body: string) {
    if (!('Notification' in window) || Notification.permission !== 'granted') return;
    const now = Date.now();
    if (now - this.lastNotif < this.COOLDOWN_MS) return;
    this.lastNotif = now;
    new Notification(title, { body, icon: '/favicon.ico', tag: `sf-${now}`, silent: false });
  }
}
