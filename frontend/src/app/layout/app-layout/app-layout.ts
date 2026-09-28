import { Component, signal, inject, computed, ChangeDetectionStrategy, DestroyRef } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet, NavigationEnd } from '@angular/router';
import { filter, map } from 'rxjs/operators';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { ThreatsService } from '../../core/services/threats.service';
import { ThreatStoreService } from '../../core/services/threat-store.service';
import { AuthService } from '../../core/services/auth';
import { canOpenUserAdmin } from '../../core/auth/permissions';
import { ThemeService } from '../../core/services/theme';
import { CommandConsole } from '../../features/command-console/command-console';
import { DemoModeService } from '../../core/services/demo-mode.service';
import { ThreatFeedService } from '../../core/services/threat-feed.service';

const PAGE_TITLES: Record<string, string> = {
  '/dashboard': 'Live Operations',
  '/threats':   'Threat Intelligence',
  '/alerts':    'Alerts',
  '/incidents': 'Incidents',
  '/map':       'Threat Map',
  '/hunting':   'Threat Hunting',
  '/rules':     'Detection Rules',
  '/admin/users': 'Users',
  '/settings':  'Settings',
};

@Component({
  selector: 'app-layout',
  standalone: true,
  imports: [RouterLink, RouterLinkActive, RouterOutlet, CommandConsole],
  templateUrl: './app-layout.html',
  styleUrl: './app-layout.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { '(document:keydown.escape)': 'closeNav()' },
})
export class AppLayout {
  readonly ws              = inject(ThreatsService);
  private store            = inject(ThreatStoreService);
  readonly alertBadge      = computed(() => this.store.newAlertCount());
  // Injected to eagerly trigger the effect() that sets data-theme on <body>.
  readonly themeService    = inject(ThemeService);
  readonly demo            = inject(DemoModeService);
  readonly feed            = inject(ThreatFeedService);
  readonly auth            = inject(AuthService);
  readonly canOpenUsers    = computed(() => canOpenUserAdmin(this.auth.currentUser()).allowed);
  readonly initials        = computed(() =>
    (this.auth.currentUser()?.display_name ?? '')
      .split(/\s+/).map(w => w[0] ?? '').join('').slice(0, 2).toUpperCase() || 'SF');
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

  /** Narrow screens: the sidebar is an off-canvas menu (CSS decides when). */
  readonly navOpen = signal(false);

  constructor() {
    this.tick();
    const timer = setInterval(() => this.tick(), 1000);
    this.destroyRef.onDestroy(() => {
      clearInterval(timer);
      this.ws.disconnect();
    });
    this.ws.connect();
    this.demo.load();
    this.feed.watch(this.destroyRef);
    // Any navigation closes the mobile menu.
    this.router.events
      .pipe(filter(e => e instanceof NavigationEnd), takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.navOpen.set(false));
  }

  toggleNav(): void {
    this.navOpen.update(open => !open);
  }

  closeNav(): void {
    this.navOpen.set(false);
  }

  logout(): void {
    this.auth.logout();
  }

  private tick() {
    this.time.set(new Date().toLocaleTimeString('he-IL', { hour12: false }));
  }
}
