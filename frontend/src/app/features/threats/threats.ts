import { Component, signal, HostListener } from '@angular/core';
import { ThreatTableComponent } from './threat-table/threat-table.component';
import { ThreatDetailDrawerComponent } from './threat-detail-drawer/threat-detail-drawer.component';

@Component({
  selector: 'app-threats',
  standalone: true,
  imports: [ThreatTableComponent, ThreatDetailDrawerComponent],
  templateUrl: './threats.html',
  styleUrl: './threats.scss',
})
export class Threats {
  selectedIp = signal<string | null>(null);
  detailWidth = signal(380);

  private dragging = false;
  private dragStartX = 0;
  private dragStartWidth = 0;

  openDrawer(ip: string) { this.selectedIp.set(ip); }
  closeDrawer()          { this.selectedIp.set(null); }

  startResize(e: MouseEvent) {
    this.dragging = true;
    this.dragStartX = e.clientX;
    this.dragStartWidth = this.detailWidth();
    e.preventDefault();
  }

  @HostListener('document:mousemove', ['$event'])
  onMouseMove(e: MouseEvent) {
    if (!this.dragging) return;
    const delta = this.dragStartX - e.clientX;
    this.detailWidth.set(Math.min(700, Math.max(240, this.dragStartWidth + delta)));
  }

  @HostListener('document:mouseup')
  onMouseUp() { this.dragging = false; }
}
