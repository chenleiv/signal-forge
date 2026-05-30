import { Injectable, signal } from '@angular/core';
import { environment } from '../../../environments/environment';

export interface AppSettings {
  wsUrl: string;
  reconnectDelay: number;
  bufferSize: number;
  criticalThreshold: number;
  highThreshold: number;
  mediumThreshold: number;
  analystName: string;
  analystRole: string;
}

const DEFAULTS: AppSettings = {
  wsUrl: environment.wsUrl,
  reconnectDelay: 3,
  bufferSize: 100,
  criticalThreshold: 80,
  highThreshold: 60,
  mediumThreshold: 40,
  analystName: 'SOC Analyst',
  analystRole: 'Tier 1',
};

const STORAGE_KEY = 'sf_settings';

@Injectable({ providedIn: 'root' })
export class SettingsService {
  readonly settings = signal<AppSettings>(this.load());

  save(patch: Partial<AppSettings>) {
    const updated = { ...this.settings(), ...patch };
    this.settings.set(updated);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
  }

  reset() {
    this.settings.set({ ...DEFAULTS });
    localStorage.removeItem(STORAGE_KEY);
  }

  private load(): AppSettings {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? { ...DEFAULTS, ...JSON.parse(raw) } : { ...DEFAULTS };
    } catch {
      return { ...DEFAULTS };
    }
  }
}
