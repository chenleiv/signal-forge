import { Component, output, input, inject, signal, computed, effect, ChangeDetectionStrategy } from '@angular/core';
import { NgClass, TitleCasePipe } from '@angular/common';
import { ExportMenuComponent } from '../../../shared/ui/export-menu.component';
import { FilterPillsComponent } from '../../../shared/ui/filter-pills.component';
import { SimulatedTagComponent } from '../../../shared/ui/simulated-tag.component';
import { ThreatStoreService } from '../../../core/services/threat-store.service';
import { downloadCsv, downloadJson, downloadMarkdown, downloadPdf } from '../../../core/utils/export.utils';

/** One row of the JSON export: typed values, stable snake_case keys. */
export interface ThreatExportItem {
  ip: string;
  avg_score: number;
  events: number;
  threat_level: string | null;
}

@Component({
  selector: 'app-threat-table',
  standalone: true,
  imports: [NgClass, TitleCasePipe, FilterPillsComponent, ExportMenuComponent, SimulatedTagComponent],
  templateUrl: './threat-table.component.html',
  styleUrl: './threat-table.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ThreatTableComponent {
  private store = inject(ThreatStoreService);

  selectedIp = input<string | null>(null);
  ipSelected = output<string>();

  readonly allRows   = computed(() => this.store.stats()?.top_ips ?? []);
  readonly loading   = signal(true);
  readonly levels = ['critical', 'high', 'medium', 'low'] as const;
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

  private readonly exportHeaders = ['IP Address', 'Avg Score', 'Events', 'Level'];
  private get exportRows(): string[][] {
    return this.filteredRows().map(r => [r.ip, String(r.score), String(r.count), r.threat_level ?? '—']);
  }

  constructor() {
    effect(() => { if (this.store.stats() !== null) this.loading.set(false); });
  }

  exportCsv() { downloadCsv(this.exportHeaders, this.exportRows, 'threats.csv'); }
  exportPdf() { downloadPdf('SignalForge — Threat Intelligence', this.exportHeaders, this.exportRows, 'threats.pdf'); }
  exportJson() { downloadJson('threats', this.exportItems, 'threats.json'); }
  exportMarkdown() { downloadMarkdown('SignalForge — Threat Intelligence', this.exportHeaders, this.exportRows, 'threats.md'); }

  private get exportItems(): ThreatExportItem[] {
    return this.filteredRows().map(r => ({
      ip: r.ip, avg_score: r.score, events: r.count, threat_level: r.threat_level ?? null,
    }));
  }

  selectIp(ip: string) { this.ipSelected.emit(ip); }

  scoreClass(score: number): string {
    if (score >= 80) return 'score-critical';
    if (score >= 60) return 'score-high';
    if (score >= 40) return 'score-medium';
    return 'score-low';
  }
}
