import { Injectable, signal } from '@angular/core';
import { environment } from '../../../environments/environment';

export interface AppSettings {
  wsUrl: string;
  reconnectDelay: number;
  bufferSize: number;
  criticalThreshold: number;
  highThreshold: number;
  mediumThreshold: number;
}

/** The configured URL, or the same host the app is served from. */
function defaultWsUrl(): string {
  if (environment.wsUrl) return environment.wsUrl;
  const scheme = location.protocol === 'https:' ? 'wss' : 'ws';
  return `${scheme}://${location.host}/ws/threats`;
}

const DEFAULTS: AppSettings = {
  wsUrl: defaultWsUrl(),
  reconnectDelay: 3,
  bufferSize: 100,
  criticalThreshold: 80,
  highThreshold: 60,
  mediumThreshold: 40,
};

// Removed fields that older saved settings may still contain.
const LEGACY_KEYS = ['analystName', 'analystRole'];

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
      if (!raw) return { ...DEFAULTS };
      const saved = JSON.parse(raw);
      for (const key of LEGACY_KEYS) delete saved[key];
      return { ...DEFAULTS, ...saved };
    } catch {
      return { ...DEFAULTS };
    }
  }
}
