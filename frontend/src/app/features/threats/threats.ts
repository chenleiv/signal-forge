import { Component, signal, HostListener, inject, OnInit, ChangeDetectionStrategy } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { ThreatTableComponent } from './threat-table/threat-table.component';
import { ThreatDetailDrawerComponent } from './threat-detail-drawer/threat-detail-drawer.component';

@Component({
  selector: 'app-threats',
  standalone: true,
  imports: [ThreatTableComponent, ThreatDetailDrawerComponent],
  templateUrl: './threats.html',
  styleUrl: './threats.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Threats implements OnInit {
  private route  = inject(ActivatedRoute);
  private router = inject(Router);

  selectedIp = signal<string | null>(null);
  drawerWidth = signal(500);

  private dragging = false;
  private dragStartX = 0;
  private dragStartWidth = 0;

  ngOnInit() {
    const ip = this.route.snapshot.queryParamMap.get('ip');
    if (ip) {
      this.selectedIp.set(ip);
      this.router.navigate([], { queryParams: {}, replaceUrl: true });
    }
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

  @HostListener('document:mousemove', ['$event'])
  onMouseMove(e: MouseEvent) {
    if (!this.dragging) return;
    const delta = this.dragStartX - e.clientX;
    this.drawerWidth.set(Math.min(700, Math.max(500, this.dragStartWidth + delta)));
  }

  @HostListener('document:mouseup')
  onMouseUp() {
    this.dragging = false;
  }
}
