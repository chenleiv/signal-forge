import { Component, signal, inject, computed, ChangeDetectionStrategy, DestroyRef } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet, NavigationEnd } from '@angular/router';
import { filter, map } from 'rxjs/operators';
import { toSignal } from '@angular/core/rxjs-interop';
import { ThreatsService } from '../../core/services/threats.service';
import { SettingsService } from '../../core/services/settings.service';
import { ThemeService } from '../../core/services/theme';
import { CommandConsole } from '../../features/command-console/command-console';

const PAGE_TITLES: Record<string, string> = {
  '/dashboard': 'Live Operations',
  '/threats':   'Threat Intelligence',
  '/alerts':    'Alerts',
  '/incidents': 'Incidents',
  '/map':       'Threat Map',
  '/hunting':   'Threat Hunting',
  '/rules':     'Detection Rules',
  '/settings':  'Settings',
};

@Component({
  selector: 'app-layout',
  standalone: true,
  imports: [RouterLink, RouterLinkActive, RouterOutlet, CommandConsole],
  templateUrl: './app-layout.html',
  styleUrl: './app-layout.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AppLayout {
  readonly ws              = inject(ThreatsService);
  readonly settingsService = inject(SettingsService);
  // Injected to eagerly trigger the effect() that sets data-theme on <body>.
  readonly themeService    = inject(ThemeService);
  private router           = inject(Router);
  private destroyRef       = inject(DestroyRef);

  private navTitle = toSignal(
    this.router.events.pipe(
      filter((e): e is NavigationEnd => e instanceof NavigationEnd),
      map(e => PAGE_TITLES[e.urlAfterRedirects] ?? 'SignalForge'),
    ),
  );

  readonly pageTitle = computed(() => this.navTitle() ?? PAGE_TITLES[this.router.url] ?? 'SignalForge');

  time = signal('');

  constructor() {
    this.tick();
    const timer = setInterval(() => this.tick(), 1000);
    this.destroyRef.onDestroy(() => {
      clearInterval(timer);
      this.ws.disconnect();
    });
    this.ws.connect();
  }

  private tick() {
    this.time.set(new Date().toLocaleTimeString('he-IL', { hour12: false }));
  }
}
