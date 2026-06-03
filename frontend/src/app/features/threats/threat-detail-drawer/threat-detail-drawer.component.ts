import {
  Component,
  output,
  inject,
  ChangeDetectionStrategy,
  signal,
  computed,
  input,
  effect,
  DestroyRef,
} from '@angular/core';
import { DatePipe, DecimalPipe, NgClass } from '@angular/common';
import { Router } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ThreatStoreService } from '../../../core/services/threat-store.service';
import { IpHistory, IpGeo, RelatedIp } from '../../../shared/models/threat.models';

@Component({
  selector: 'app-threat-detail-drawer',
  standalone: true,
  imports: [DatePipe, DecimalPipe, NgClass],
  templateUrl: './threat-detail-drawer.component.html',
  styleUrl: './threat-detail-drawer.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ThreatDetailDrawerComponent {
  // ── inputs / outputs ──────────────────────────────────────────
  ip       = input<string | null>(null);
  closed   = output<void>();
  ipChange = output<string>();

  // ── public signals ────────────────────────────────────────────
  history        = signal<IpHistory | null>(null);
  loading        = signal(false);
  aiSummary      = signal<string | null>(null);
  aiLoading      = signal(false);
  geoData        = signal<IpGeo | null>(null);
  relatedIps     = signal<RelatedIp[]>([]);
  geoOpen        = signal(true);
  abuseOpen      = signal(false);
  attackOpen     = signal(true);
  aiOpen         = signal(false);
  mitreOpen      = signal(false);
  relatedOpen    = signal(false);
  eventsOpen     = signal(true);
  isBlocked      = signal(false);
  existingCaseId = signal<string | null>(null);
  eventFilter    = signal('');
  typeFilter     = signal('all');

  readonly filteredEvents = computed(() => {
    const events = this.history()?.events ?? [];
    const q      = this.eventFilter().toLowerCase();
    const type   = this.typeFilter();
    return events.filter(e =>
      (type === 'all' || e.attack_type === type) &&
      (!q || e.attack_type.toLowerCase().includes(q) || e.score.toString().includes(q))
    );
  });

  readonly attackTypes = computed(() =>
    [...new Set((this.history()?.events ?? []).map(e => e.attack_type))]
  );

  // ── private injections ────────────────────────────────────────
  private readonly store      = inject(ThreatStoreService);
  private readonly router     = inject(Router);
  private readonly destroyRef = inject(DestroyRef);

  // ── private state ─────────────────────────────────────────────
  private readonly summaryCache = new Map<string, string | null>();

  // ── constructor ───────────────────────────────────────────────
  constructor() {
    effect(() => {
      const ip = this.ip();
      if (!ip) return;

      this.history.set(null);
      this.geoData.set(null);
      this.relatedIps.set([]);
      this.geoOpen.set(true);
      this.abuseOpen.set(false);
      this.attackOpen.set(true);
      this.aiOpen.set(false);
      this.mitreOpen.set(false);
      this.relatedOpen.set(false);
      this.eventsOpen.set(true);
      this.loading.set(true);
      this.aiSummary.set(null);
      this.existingCaseId.set(null);
      this.eventFilter.set('');
      this.typeFilter.set('all');

      this.store.fetchIpHistory(ip)
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe({ next: h => { this.history.set(h); this.loading.set(false); }, error: () => this.loading.set(false) });

      const cached = this.summaryCache.get(ip);
      if (cached !== undefined) {
        this.aiSummary.set(cached);
        this.aiLoading.set(false);
      } else {
        this.aiLoading.set(true);
        this.store.fetchAiSummary(ip)
          .pipe(takeUntilDestroyed(this.destroyRef))
          .subscribe({
            next:  res => { this.summaryCache.set(ip, res.summary); this.aiSummary.set(res.summary); this.aiLoading.set(false); },
            error: ()  => this.aiLoading.set(false),
          });
      }

      this.store.fetchIpGeo(ip)
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe({ next: g => this.geoData.set(g), error: () => {} });

      this.store.fetchRelatedIps(ip)
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe({ next: r => this.relatedIps.set(r.related), error: () => {} });

      this.store.getBlockStatus(ip)
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe({ next: r => this.isBlocked.set(r.blocked), error: () => {} });

      this.store.getIpCase(ip)
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe({ next: r => this.existingCaseId.set(r.case_id), error: () => {} });
    });
  }

  // ── public methods ────────────────────────────────────────────
  close() { this.closed.emit(); }

  huntIp() {
    const ip = this.ip();
    if (ip) this.router.navigate(['/hunting'], { queryParams: { ip } });
  }

  createCase() {
    const ip = this.ip();
    if (!ip) return;
    const existingId = this.existingCaseId();
    if (existingId) {
      this.router.navigate(['/incidents'], { queryParams: { id: existingId } });
      return;
    }
    this.store.createCaseFromIp(ip)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(res => {
        this.existingCaseId.set(res.id);
        this.router.navigate(['/incidents'], {
          queryParams: { id: res.id, ...(res['existing'] ? { existing: '1' } : {}) },
        });
      });
  }

  toggleBlock() {
    const ip = this.ip();
    if (!ip) return;
    const action = this.isBlocked() ? this.store.unblockIp(ip) : this.store.blockIp(ip);
    action.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(r => this.isBlocked.set(r.blocked));
  }

  selectRelated(ip: string) { this.ipChange.emit(ip); }

  scoreColor(score: number): string {
    if (score >= 80) return '#ef4444';
    if (score >= 60) return '#f97316';
    if (score >= 40) return '#f59e0b';
    return '#60a5fa';
  }

  countryFlag(code: string): string {
    return code.toUpperCase().replace(/./g, c =>
      String.fromCodePoint(0x1F1E6 - 65 + c.charCodeAt(0))
    );
  }
}
