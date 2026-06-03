import { Component, inject, signal, ChangeDetectionStrategy } from '@angular/core';
import { SettingsService, AppSettings } from '../../core/services/settings.service';
import { AuthService } from '../../core/services/auth';
import { ThemeService } from '../../core/services/theme';

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [],
  templateUrl: './settings.html',
  styleUrl: './settings.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Settings {
  private svc = inject(SettingsService);
  private auth = inject(AuthService);
  readonly themeService = inject(ThemeService);

  form = signal<AppSettings>({ ...this.svc.settings() });

  saved = signal(false);

  save() {
    this.svc.save(this.form());
    this.saved.set(true);
    setTimeout(() => this.saved.set(false), 2000);
  }

  reset() {
    this.svc.reset();
    this.form.set({ ...this.svc.settings() });
  }

  logout() {
    this.auth.logout();
  }
}
