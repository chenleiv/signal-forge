import {
  Component,
  Input,
  OnChanges,
  OnDestroy,
  SimpleChanges,
  output,
  inject,
  ChangeDetectionStrategy,
} from '@angular/core';
import { DatePipe } from '@angular/common';
import { Subject, Subscription } from 'rxjs';
import { switchMap } from 'rxjs/operators';
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
export class ThreatDetailDrawerComponent implements OnChanges, OnDestroy {
  @Input() ip: string | null = null;
  closed = output<void>();

  private store = inject(ThreatStoreService);

  history: IpHistory | null = null;
  loading = false;

  private ipChange$ = new Subject<string>();
  private sub: Subscription = this.ipChange$
    .pipe(
      switchMap((ip) => {
        this.loading = true;
        this.history = null;
        return this.store.fetchIpHistory(ip);
      }),
    )
    .subscribe({
      next: (h) => {
        this.history = h;
        this.loading = false;
      },
      error: () => {
        this.loading = false;
      },
    });

  ngOnChanges(changes: SimpleChanges) {
    if (changes['ip'] && this.ip) {
      this.ipChange$.next(this.ip);
    }
  }

  ngOnDestroy() {
    this.sub.unsubscribe();
    this.ipChange$.complete();
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
