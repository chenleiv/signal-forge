import {
  Component,
  output,
  inject,
  ChangeDetectionStrategy,
  signal,
  input,
  effect,
  DestroyRef,
} from '@angular/core';
import { DatePipe } from '@angular/common';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ThreatStoreService } from '../../../core/services/threat-store.service';
import { IpHistory } from '../../../shared/models/threat.models';

@Component({
  selector: 'app-threat-detail-drawer',
  standalone: true,
  imports: [DatePipe],
  templateUrl: './threat-detail-drawer.component.html',
  styleUrl: './threat-detail-drawer.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ThreatDetailDrawerComponent {
  ip = input<string | null>(null);
  closed = output<void>();

  private store = inject(ThreatStoreService);
  private destroyRef = inject(DestroyRef);

  history = signal<IpHistory | null>(null);
  loading = signal(false);
  aiSummary = signal<string | null>(null);
  aiLoading = signal(false);

  constructor() {
    effect(() => {
      const ip = this.ip();
      if (!ip) return;

      this.history.set(null);
      this.loading.set(true);
      this.aiSummary.set(null);
      this.aiLoading.set(true);

      this.store
        .fetchIpHistory(ip)
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe({
          next: (h) => {
            this.history.set(h);
            this.loading.set(false);
          },
          error: () => this.loading.set(false),
        });

      this.store
        .fetchAiSummary(ip)
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe({
          next: (res) => {
            this.aiSummary.set(res.summary);
            this.aiLoading.set(false);
          },
          error: () => this.aiLoading.set(false),
        });
    });
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
