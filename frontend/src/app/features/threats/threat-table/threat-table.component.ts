import { Component, OnInit, output, input, inject, signal, computed, DestroyRef, HostListener } from '@angular/core';
import { NgClass, TitleCasePipe } from '@angular/common';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { HttpClient } from '@angular/common/http';
import { ThreatStats } from '../../../shared/models/threat.models';
import { downloadCsv, downloadPdf } from '../../../core/utils/export.utils';

interface IpRow {
  ip: string;
  count: number;
  score: number;
  threat_level?: string;
}

@Component({
  selector: 'app-threat-table',
  standalone: true,
  imports: [NgClass, TitleCasePipe],
  templateUrl: './threat-table.component.html',
  styleUrl: './threat-table.component.scss',
})
export class ThreatTableComponent implements OnInit {
  private destroyRef = inject(DestroyRef);
  protected readonly http = inject(HttpClient);

  protected allRows = signal<IpRow[]>([]);
  loading = true;

  searchIp    = signal('');
  levelFilter = signal('all');

  readonly filteredRows = computed(() => {
    const search = this.searchIp().toLowerCase();
    const level  = this.levelFilter();
    return this.allRows().filter(r =>
      (!search || r.ip.toLowerCase().includes(search)) &&
      (level === 'all' || r.threat_level === level)
    );
  });

  selectedIp = input<string | null>(null);
  ipSelected = output<string>();

  ngOnInit() {
    this.http
      .get<ThreatStats>('/api/stats')
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (stats) => {
          this.allRows.set(stats.top_ips);
          this.loading = false;
        },
        error: () => {
          this.loading = false;
        },
      });
  }

  exportOpen = signal(false);

  private readonly exportHeaders = ['IP Address', 'Avg Score', 'Events', 'Level'];

  private get exportRows(): string[][] {
    return this.filteredRows().map(r => [r.ip, String(r.score), String(r.count), r.threat_level ?? '—']);
  }

  exportCsv() {
    downloadCsv(this.exportHeaders, this.exportRows, 'threats.csv');
    this.exportOpen.set(false);
  }

  exportPdf() {
    downloadPdf('SignalForge — Threat Intelligence', this.exportHeaders, this.exportRows, 'threats.pdf');
    this.exportOpen.set(false);
  }

  @HostListener('document:click', ['$event'])
  onDocClick(e: MouseEvent) {
    if (!(e.target as HTMLElement).closest('.export-wrap')) {
      this.exportOpen.set(false);
    }
  }

  selectIp(ip: string) {
    this.ipSelected.emit(ip);
  }

  scoreClass(score: number): string {
    if (score >= 80) return 'score-critical';
    if (score >= 60) return 'score-high';
    if (score >= 40) return 'score-medium';
    return 'score-low';
  }
}
