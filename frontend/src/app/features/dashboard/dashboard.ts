import {
  Component,
  computed,
  inject,
  ChangeDetectionStrategy,
  signal,
  effect,
} from '@angular/core';
import { DatePipe, NgClass } from '@angular/common';
import { RouterLink } from '@angular/router';
import { NgxEchartsDirective } from 'ngx-echarts';
import { EChartsOption } from 'echarts';
import { ThreatStoreService } from '../../core/services/threat-store.service';
import { ThemeService } from '../../core/services/theme';
import { ThreatStats } from '../../shared/models/threat.models';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [DatePipe, NgClass, NgxEchartsDirective, RouterLink],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Dashboard {
  // ── public signals ────────────────────────────────────────────
  severityChart = signal<EChartsOption | null>(null);
  attackChart   = signal<EChartsOption | null>(null);
  regionChart   = signal<EChartsOption | null>(null);
  topIpsChart   = signal<EChartsOption | null>(null);

  readonly criticalEvents = computed(() =>
    this.store.events().filter(e => e.threat_level === 'critical').slice(0, 30)
  );

  // ── private injections ────────────────────────────────────────
  protected readonly store = inject(ThreatStoreService);
  private readonly themeService = inject(ThemeService);

  constructor() {
    effect(() => {
      const isLight = this.themeService.theme() === 'light';
      const stats = this.store.stats();
      const events = this.store.events();
      if (!stats) return;

      const pal = this.palette(isLight);

      const sevTotal = Object.values(stats.severity_counts).reduce((s, n) => s + n, 0);
      this.severityChart.set(
        this.buildDonut(
          'THREATS BY SEVERITY',
          [
            { name: 'Critical', value: stats.severity_counts['critical'] ?? 0, color: '#ef4444' },
            { name: 'High', value: stats.severity_counts['high'] ?? 0, color: '#f97316' },
            { name: 'Medium', value: stats.severity_counts['medium'] ?? 0, color: '#f59e0b' },
            { name: 'Low', value: stats.severity_counts['low'] ?? 0, color: '#60a5fa' },
          ],
          sevTotal,
          'Events',
          pal,
        ),
      );

      const atkColors = ['#ef4444', '#f97316', '#f59e0b', '#60a5fa', '#a855f7'];
      const atkData = Object.entries(stats.attack_types).map(([k, v], i) => ({
        name: k,
        value: v as number,
        color: atkColors[i % 5],
      }));
      this.attackChart.set(
        this.buildDonut(
          'ATTACK TYPES',
          atkData,
          atkData.reduce((s, d) => s + d.value, 0),
          'Events',
          pal,
        ),
      );

      const regionMap: Record<string, string> = {
        US: '#60a5fa',
        EU: '#22c55e',
        RU: '#ef4444',
        CN: '#f97316',
        IL: '#a855f7',
        BR: '#f59e0b',
      };
      const regionCounts = events.reduce(
        (acc, e) => {
          acc[e.region] = (acc[e.region] || 0) + 1;
          return acc;
        },
        {} as Record<string, number>,
      );
      const regData = Object.entries(regionCounts).map(([k, v]) => ({
        name: k,
        value: v,
        color: regionMap[k] ?? '#9ca3af',
      }));
      this.regionChart.set(
        this.buildDonut(
          'BY REGION',
          regData,
          regData.reduce((s, d) => s + d.value, 0),
          'Events',
          pal,
        ),
      );

      this.topIpsChart.set(this.buildTopIps(stats, pal));
    });
  }

  private palette(isLight: boolean) {
    return {
      text:     isLight ? '#475569' : '#6b7280',
      text2:    isLight ? '#64748b' : '#9ca3af',
      textMain: isLight ? '#1e293b' : '#e5e7eb',
      muted:    isLight ? '#94a3b8' : '#4b5563',
      gridLine: isLight ? '#e2e8f0' : '#151c2b',
    };
  }

  private buildDonut(
    title: string,
    data: { name: string; value: number; color: string }[],
    total: number,
    centerLabel: string,
    pal: ReturnType<Dashboard['palette']>,
  ): EChartsOption {
    return {
      backgroundColor: 'transparent',
      textStyle: { color: pal.text, fontFamily: 'Inter, system-ui, sans-serif', fontSize: 10 },
      title: {
        text: title,
        textStyle: { color: pal.text2, fontSize: 9, fontWeight: 600 },
        top: 8,
        left: 12,
      },
      graphic: [
        {
          type: 'text',
          left: 'center',
          top: '36%',
          style: {
            text: total.toString(),
            fontSize: 22,
            fontWeight: 'bold',
            fill: pal.textMain,
            font: 'bold 22px JetBrains Mono, monospace',
          },
        },
        {
          type: 'text',
          left: 'center',
          top: '52%',
          style: { text: centerLabel, fontSize: 10, fill: pal.muted },
        },
      ],
      legend: {
        bottom: 4,
        textStyle: { color: pal.text, fontSize: 9 },
        itemWidth: 8,
        itemHeight: 8,
      },
      series: [
        {
          type: 'pie',
          radius: ['44%', '64%'],
          center: ['50%', '46%'],
          data: data.map((d) => ({ name: d.name, value: d.value, itemStyle: { color: d.color } })),
          label: { show: false },
          emphasis: { label: { show: true, color: pal.textMain, fontSize: 11, fontWeight: 'bold' } },
        },
      ],
    };
  }

  private buildTopIps(stats: ThreatStats, pal: ReturnType<Dashboard['palette']>): EChartsOption {
    const top = stats.top_ips.slice(0, 6);
    return {
      backgroundColor: 'transparent',
      textStyle: { color: pal.text, fontFamily: 'Inter, system-ui, sans-serif', fontSize: 10 },
      title: {
        text: 'TOP ATTACKING IPs',
        textStyle: { color: pal.text2, fontSize: 9, fontWeight: 600 },
        top: 8,
        left: 12,
      },
      grid: { top: 36, bottom: 20, left: 10, right: 44, containLabel: true },
      xAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: pal.gridLine } },
        axisLine: { show: false },
        axisLabel: { show: false },
      },
      yAxis: {
        type: 'category',
        data: top.map(x => x.ip),
        axisLabel: { color: pal.text, fontSize: 9 },
      },
      series: [
        {
          type: 'bar',
          data: top.map(x => ({
            value: x.count,
            itemStyle: { color: '#3b82f6', borderRadius: [0, 3, 3, 0] },
          })),
          barMaxWidth: 14,
          label: { show: true, position: 'right', color: pal.text2, fontSize: 9 },
        },
      ],
    };
  }

  getSeverityClass(level: string): string {
    return `sev-${level}`;
  }

  getEventLabel(attackType: string): string {
    const labels: Record<string, string> = {
      SQLi: 'SQL Injection attempt',
      DDoS: 'DDoS flood detected',
      BruteForce: 'Brute force login',
      PortScan: 'Port scan observed',
      Malware: 'Malware beacon',
    };
    return labels[attackType] ?? 'Unknown event';
  }
}
