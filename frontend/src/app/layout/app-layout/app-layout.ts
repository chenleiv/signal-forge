import { Component, OnInit, OnDestroy, signal, inject } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet, NavigationEnd } from '@angular/router';
import { filter } from 'rxjs/operators';
import { ThreatsService } from '../../core/services/threats.service';

const PAGE_TITLES: Record<string, string> = {
  '/dashboard': 'Live Operations',
  '/threats': 'Threat Intelligence',
  '/alerts': 'Alerts',
  '/incidents': 'Incidents',
  '/map': 'Threat Map',
  '/settings': 'Settings',
};

@Component({
  selector: 'app-layout',
  standalone: true,
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  templateUrl: './app-layout.html',
  styleUrl: './app-layout.scss',
})
export class AppLayout implements OnInit, OnDestroy {
  private ws = inject(ThreatsService);
  private router = inject(Router);

  time = signal('');
  pageTitle = signal('Live Operations');

  private timer: ReturnType<typeof setInterval> | null = null;

  constructor() {
    this.router.events.pipe(filter((e) => e instanceof NavigationEnd)).subscribe((e: any) => {
      this.pageTitle.set(PAGE_TITLES[e.urlAfterRedirects] ?? 'SignalForge');
    });
  }

  ngOnInit() {
    this.tick();
    this.timer = setInterval(() => this.tick(), 1000);
    this.ws.connect();
    this.pageTitle.set(PAGE_TITLES[this.router.url] ?? 'SignalForge');
  }

  ngOnDestroy() {
    if (this.timer) clearInterval(this.timer);
    this.ws.disconnect();
  }

  private tick() {
    this.time.set(new Date().toLocaleTimeString('he-IL', { hour12: false }));
  }
}
