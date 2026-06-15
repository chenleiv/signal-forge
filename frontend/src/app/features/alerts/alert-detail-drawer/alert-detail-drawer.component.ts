import {
  Component,
  input,
  output,
  inject,
  signal,
  ChangeDetectionStrategy,
  DestroyRef,
} from '@angular/core';
import { DatePipe } from '@angular/common';
import { Router } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ThreatStoreService } from '../../../core/services/threat-store.service';
import { ThreatAlert, DETECTION_SOURCE_LABELS, SEVERITY_COLORS, scoreToColor } from '../../../shared/models/threat.models';

@Component({
  selector: 'app-alert-detail-drawer',
  standalone: true,
  imports: [DatePipe],
  templateUrl: './alert-detail-drawer.component.html',
  styleUrl:    './alert-detail-drawer.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AlertDetailDrawerComponent {
  alert        = input<ThreatAlert | null>(null);
  closed       = output<void>();
  caseCreated  = output<string>();

  readonly creatingCase = signal(false);
  readonly caseId       = signal<string | null>(null);

  readonly severityColor  = (sev: string) => SEVERITY_COLORS[sev] ?? SEVERITY_COLORS['low'];
  readonly detectionLabel = (src: string) => DETECTION_SOURCE_LABELS[src] ?? src;

  private readonly store      = inject(ThreatStoreService);
  private readonly router     = inject(Router);
  private readonly destroyRef = inject(DestroyRef);

  close() { this.closed.emit(); }

  createCase() {
    const a = this.alert();
    if (!a) return;
    if (this.caseId()) {
      this.router.navigate(['/incidents'], { queryParams: { id: this.caseId() } });
      return;
    }
    this.creatingCase.set(true);
    this.store.createCaseFromAlert(a.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: inc => {
          this.creatingCase.set(false);
          this.caseId.set(inc.id);
          this.caseCreated.emit(inc.id);
          this.router.navigate(['/incidents'], { queryParams: { id: inc.id } });
        },
        error: () => this.creatingCase.set(false),
      });
  }

  readonly riskColor = scoreToColor;

  riskLabel(score: number): string {
    if (score >= 80) return 'Critical';
    if (score >= 60) return 'High';
    if (score >= 40) return 'Medium';
    return 'Low';
  }

  timelineIcon(type: string): string {
    const map: Record<string, string> = {
      detection: '◎',
      attempt:   '✕',
      behavior:  '◆',
      alert:     '▲',
      response:  '✓',
    };
    return map[type] ?? '•';
  }
}
