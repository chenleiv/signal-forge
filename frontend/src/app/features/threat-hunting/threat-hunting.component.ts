import {
  Component,
  inject,
  signal,
  computed,
  ChangeDetectionStrategy,
  DestroyRef,
} from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, ActivatedRoute } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ThreatStoreService } from '../../core/services/threat-store.service';
import { HuntQuery, HuntResult, SavedHunt, ATTACK_TYPES, REGIONS, scoreToColor } from '../../shared/models/threat.models';

@Component({
  selector: 'app-threat-hunting',
  standalone: true,
  imports: [DatePipe, FormsModule],
  templateUrl: './threat-hunting.component.html',
  styleUrl:    './threat-hunting.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ThreatHuntingComponent {
  // ── public signals ────────────────────────────────────────────
  ip          = signal('');
  attack_type = signal('');
  region      = signal('');
  min_score   = signal(0);
  max_score   = signal(100);
  results     = signal<HuntResult[]>([]);
  total       = signal(0);
  running     = signal(false);
  hasRun      = signal(false);
  savedHunts  = signal<SavedHunt[]>([]);
  saveName    = signal('');
  showSave    = signal(false);

  readonly query = computed<HuntQuery>(() => ({
    ip:          this.ip()          || undefined,
    attack_type: this.attack_type() || undefined,
    region:      this.region()      || undefined,
    min_score:   this.min_score(),
    max_score:   this.max_score(),
  }));

  readonly attackTypes = ATTACK_TYPES;
  readonly regions     = REGIONS;

  // ── private injections ────────────────────────────────────────
  private readonly store      = inject(ThreatStoreService);
  private readonly router     = inject(Router);
  private readonly route      = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);

  // ── constructor ───────────────────────────────────────────────
  constructor() {
    this.store.getSavedHunts()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(h => this.savedHunts.set(h));

    const ip = this.route.snapshot.queryParamMap.get('ip');
    if (ip) {
      this.ip.set(ip);
      this.router.navigate([], { queryParams: {}, replaceUrl: true });
      this.run();
    }
  }

  // ── public methods ────────────────────────────────────────────
  run() {
    this.running.set(true);
    this.store.runHunt(this.query())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: r => { this.results.set(r.results); this.total.set(r.total); this.running.set(false); this.hasRun.set(true); },
        error: () => this.running.set(false),
      });
  }

  clear() {
    this.ip.set('');
    this.attack_type.set('');
    this.region.set('');
    this.min_score.set(0);
    this.max_score.set(100);
    this.results.set([]);
    this.total.set(0);
    this.hasRun.set(false);
  }

  saveHunt() {
    const name = this.saveName().trim();
    if (!name) return;
    this.store.saveHunt(name, this.query(), this.total())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(h => { this.savedHunts.update(list => [h, ...list]); this.saveName.set(''); this.showSave.set(false); });
  }

  loadHunt(hunt: SavedHunt) {
    const q = hunt.query;
    this.ip.set(q.ip ?? '');
    this.attack_type.set(q.attack_type ?? '');
    this.region.set(q.region ?? '');
    this.min_score.set(q.min_score ?? 0);
    this.max_score.set(q.max_score ?? 100);
    this.run();
  }

  deleteHunt(id: string, e: Event) {
    e.stopPropagation();
    this.store.deleteHunt(id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.savedHunts.update(list => list.filter(h => h.id !== id)));
  }

  investigateIp(ip: string) { this.router.navigate(['/threats'], { queryParams: { ip } }); }

  readonly scoreColor = scoreToColor;
}
