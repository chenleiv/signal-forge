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
    '(document:mousemove)': 'onMouseMove($event)',
    '(document:mouseup)': 'onMouseUp()',
  },
})
export class Threats {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private destroyRef = inject(DestroyRef);

  selectedIp = signal<string | null>(null);
  drawerWidth = signal(500);

  private dragging = false;
  private dragStartX = 0;
  private dragStartWidth = 0;

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

  startResize(e: MouseEvent) {
    this.dragging = true;
    this.dragStartX = e.clientX;
    this.dragStartWidth = this.drawerWidth();
    e.preventDefault();
    e.stopPropagation();
  }

  onMouseMove(e: MouseEvent) {
    if (!this.dragging) return;
    const delta = this.dragStartX - e.clientX;
    this.drawerWidth.set(Math.min(700, Math.max(500, this.dragStartWidth + delta)));
  }

  onMouseUp() {
    this.dragging = false;
  }
}
