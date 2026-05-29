import { Component, inject, effect, signal, input, ChangeDetectionStrategy } from '@angular/core';
import { NgxEchartsDirective } from 'ngx-echarts';
import { EChartsOption } from 'echarts';
import { ThreatStoreService } from '../../../core/services/threat-store.service';
import { AttackType, ThreatLevel, ThreatStats } from '../../../shared/models/threat.models';

@Component({
  selector: 'app-charts-column',
  standalone: true,
  imports: [NgxEchartsDirective],
  templateUrl: './charts-column.component.html',
  styleUrl: './charts-column.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ChartsColumnComponent {
  readonly column = input<'left' | 'right'>('left');

  private readonly store = inject(ThreatStoreService);

  topChart = signal<EChartsOption | null>(null);
  bottomChart = signal<EChartsOption | null>(null);

  private readonly BASE_OPTS: EChartsOption = {
    backgroundColor: '#13171f',
    grid: { top: 32, bottom: 24, left: 8, right: 8, containLabel: true },
    textStyle: { color: '#6b7280', fontFamily: 'Inter, system-ui, sans-serif', fontSize: 10 },
  };

  constructor() {
    effect(() => {
      const stats = this.store.stats();
      if (!stats) return;

      if (this.column() === 'left') {
        this.topChart.set(this.buildSeverityChart(stats));
        this.bottomChart.set(this.buildAttackTypesChart(stats));
      } else {
        this.topChart.set(this.buildEpmChart(stats));
        this.bottomChart.set(this.buildTopIpsChart(stats));
      }
    });
  }

  private buildSeverityChart(stats: ThreatStats): EChartsOption {
    const levels = ['critical', 'high', 'medium', 'low'];
    const colors = ['#ff2d55', '#ff6b00', '#ffcc00', '#00d4ff'];
    const counts = levels.map((l) => stats.severity_counts[l as ThreatLevel] ?? 0);

    return {
      ...this.BASE_OPTS,
      title: { text: 'THREATS BY SEVERITY', textStyle: { color: '#9ca3af', fontSize: 10, fontWeight: 600 } },
      xAxis: {
        type: 'value',
        axisLine: { lineStyle: { color: '#1e2535' } },
        splitLine: { lineStyle: { color: '#151c2b' } },
      },
      yAxis: {
        type: 'category',
        data: levels.map((l) => l.toUpperCase()),
        axisLabel: { color: '#6b7280' },
      },
      series: [
        {
          type: 'bar',
          data: counts.map((v, i) => ({ value: v, itemStyle: { color: colors[i] } })),
          barMaxWidth: 20,
          label: { show: true, position: 'right', color: '#fff', fontSize: 10 },
        },
      ],
    };
  }

  private buildAttackTypesChart(stats: ThreatStats): EChartsOption {
    const types = Object.keys(stats.attack_types);
    const colors = ['#ff2d55', '#ff6b00', '#ffcc00', '#00d4ff', '#a855f7'];
    const data = types.map((t, i) => ({
      name: t,
      value: stats.attack_types[t as AttackType],
      itemStyle: { color: colors[i % colors.length] },
    }));

    return {
      ...this.BASE_OPTS,
      title: { text: 'ATTACK TYPES', textStyle: { color: '#9ca3af', fontSize: 10 } },
      legend: { bottom: 0, textStyle: { color: '#6b7280', fontSize: 9 }, itemWidth: 10 },
      series: [
        {
          type: 'pie',
          radius: ['40%', '70%'],
          center: ['50%', '50%'],
          data,
          label: { show: false },
          emphasis: { label: { show: true, color: '#fff', fontSize: 11 } },
        },
      ],
    };
  }

  private buildEpmChart(stats: ThreatStats): EChartsOption {
    const buckets = stats.events_per_min ?? [];
    return {
      ...this.BASE_OPTS,
      title: { text: 'EVENTS PER MINUTE', textStyle: { color: '#9ca3af', fontSize: 10 } },
      xAxis: {
        type: 'category',
        data: buckets.map((b: any) => b.minute),
        axisLabel: { color: '#6b7280', fontSize: 9 },
        axisLine: { lineStyle: { color: '#1e2535' } },
      },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: '#151c2b' } } },
      series: [
        {
          type: 'line',
          data: buckets.map((b: any) => b.count),
          smooth: true,
          lineStyle: { color: '#3b82f6', width: 2 },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(59, 130, 246, 0.2)' },
                { offset: 1, color: 'rgba(59, 130, 246, 0)' },
              ],
            },
          },
          symbol: 'none',
        },
      ],
    };
  }

  private buildTopIpsChart(stats: ThreatStats): EChartsOption {
    const top = (stats.top_ips ?? []).slice(0, 8);
    return {
      ...this.BASE_OPTS,
      title: { text: 'TOP ATTACKING IPs', textStyle: { color: '#9ca3af', fontSize: 10 } },
      xAxis: {
        type: 'value',
        axisLine: { lineStyle: { color: '#1e2535' } },
        splitLine: { lineStyle: { color: '#151c2b' } },
      },
      yAxis: {
        type: 'category',
        data: top.map((x: any) => x.ip),
        axisLabel: { color: '#6b7280', fontSize: 9 },
      },
      series: [
        {
          type: 'bar',
          data: top.map((x: any) => ({ value: x.count, itemStyle: { color: '#2563eb' } })),
          barMaxWidth: 16,
          label: { show: true, position: 'right', color: '#fff', fontSize: 9 },
        },
      ],
    };
  }
}
