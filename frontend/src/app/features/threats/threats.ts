import { Component, signal } from '@angular/core';
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

  openDrawer(ip: string) { this.selectedIp.set(ip); }
  closeDrawer()          { this.selectedIp.set(null); }
}
