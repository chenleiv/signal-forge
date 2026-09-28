import { DrawerResize } from '../../shared/ui/drawer-resize';
import { Component, signal, inject, ChangeDetectionStrategy, DestroyRef } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ThreatTableComponent } from './threat-table/threat-table.component';
import { ThreatDetailDrawerComponent } from './threat-detail-drawer/threat-detail-drawer.component';

@Component({
  selector: 'app-threats',
  standalone: true,
  imports: [ThreatTableComponent, ThreatDetailDrawerComponent],
  templateUrl: './threats.html',
  styleUrl: './threats.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    '(document:mousemove)': 'drawer.move($event)',
    '(document:mouseup)': 'drawer.end()',
  },
})
export class Threats {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private destroyRef = inject(DestroyRef);

  selectedIp = signal<string | null>(null);
  readonly drawer = new DrawerResize(500, 500, 700);

  constructor() {
    this.route.queryParamMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe((params) => {
      const ip = params.get('ip');
      if (ip) {
        this.selectedIp.set(ip);
        this.router.navigate([], { queryParams: {}, replaceUrl: true });
      }
    });
  }

  openDrawer(ip: string) {
    this.selectedIp.set(ip);
  }
  closeDrawer() {
    this.selectedIp.set(null);
  }

}
