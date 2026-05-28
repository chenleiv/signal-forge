import { Component, Input, OnChanges, SimpleChanges, output, inject } from '@angular/core';
import { DatePipe } from '@angular/common';
import { ThreatStoreService } from '../../../core/services/threat-store.service';
import { IpHistory } from '../../../shared/models/threat.models';

@Component({
  selector: 'app-threat-detail-drawer',
  standalone: true,
  imports: [DatePipe],
  templateUrl: './threat-detail-drawer.component.html',
  styleUrl: './threat-detail-drawer.component.scss',
})
export class ThreatDetailDrawerComponent implements OnChanges {
  @Input() ip: string | null = null;

  closed = output<void>();

  private store = inject(ThreatStoreService);

  history: IpHistory | null = null;
  loading = false;

  ngOnChanges(changes: SimpleChanges) {
    if (changes['ip'] && this.ip) {
      this.loading = true;
      this.history = null;
      this.store.fetchIpHistory(this.ip).subscribe({
        next: (h) => { this.history = h; this.loading = false; },
        error: () => { this.loading = false; },
      });
    }
  }

  close() {
    this.closed.emit();
  }

  scoreColor(score: number): string {
    if (score >= 80) return '#ff2d55';
    if (score >= 60) return '#ff6b00';
    if (score >= 40) return '#ffcc00';
    return '#00d4ff';
  }
}
