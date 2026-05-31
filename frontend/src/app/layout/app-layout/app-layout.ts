import { Component, OnInit, OnDestroy, signal, inject, computed } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet, NavigationEnd } from '@angular/router';
import { filter, map } from 'rxjs/operators';
import { ThreatsService } from '../../core/services/threats.service';
import { SettingsService } from '../../core/services/settings.service';
import { toSignal } from '@angular/core/rxjs-interop';
import { CommandConsole } from '../../features/command-console/command-console';

const PAGE_TITLES: Record<string, string> = {
  '/dashboard': 'Live Operations',
  '/threats':   'Threat Intelligence',
  '/alerts':    'Alerts',
  '/incidents': 'Incidents',
  '/map':       'Threat Map',
  '/network':   'Network Graph',
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
})
export class AppLayout implements OnInit, OnDestroy {
  readonly ws = inject(ThreatsService);
  private router = inject(Router);
  readonly settingsService = inject(SettingsService);

  private navTitle = toSignal(
    this.router.events.pipe(
      filter((e) => e instanceof NavigationEnd),
      map((e: NavigationEnd) => PAGE_TITLES[e.urlAfterRedirects] ?? 'SignalForge'),
    ),
  );

  readonly pageTitle = computed(
    () => this.navTitle() ?? PAGE_TITLES[this.router.url] ?? 'SignalForge',
  );

  time = signal('');
  private timer: ReturnType<typeof setInterval> | null = null;

  ngOnInit() {
    this.tick();
    this.timer = setInterval(() => this.tick(), 1000);
    this.ws.connect();
  }

  ngOnDestroy() {
    if (this.timer) clearInterval(this.timer);
    this.ws.disconnect();
  }

  private tick() {
    this.time.set(new Date().toLocaleTimeString('he-IL', { hour12: false }));
  }
}
