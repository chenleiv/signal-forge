import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { SettingsService, AppSettings } from '../../core/services/settings.service';

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './settings.html',
  styleUrl: './settings.scss',
})
export class Settings {
  private svc = inject(SettingsService);

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
}
