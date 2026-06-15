import {
  Component,
  ElementRef,
  inject,
  effect,
  afterNextRender,
  DestroyRef,
  ChangeDetectionStrategy,
  signal,
} from '@angular/core';
import { ThreatStoreService } from '../../core/services/threat-store.service';
import { SEVERITY_COLORS, ThreatEvent } from '../../shared/models/threat.models';
import * as d3 from 'd3';
import * as topojson from 'topojson-client';

@Component({
  selector: 'app-threat-map',
  standalone: true,
  templateUrl: './threat-map.html',
  styleUrl: './threat-map.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ThreatMap {
  private el = inject(ElementRef);
  private store = inject(ThreatStoreService);
  readonly filterLevel = signal<string>('all');

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  private svg: d3.Selection<SVGSVGElement, unknown, any, any> | null = null;
  private projection: d3.GeoProjection | null = null;

  constructor() {
    afterNextRender(() => this.initMap());

    inject(DestroyRef).onDestroy(() => {
      this.svg?.remove();
      this.svg = null;
    });

    effect(() => {
      const events = this.store.events();
      const filter = this.filterLevel();
      if (events.length > 0 && this.svg && this.projection) {
        const event = events[0];
        if (filter === 'all' || event.threat_level === filter) {
          this.drawAttack(event);
        }
      }
    });
  }

  setFilterLevel(level: string) {
    this.filterLevel.set(level);
  }

  private async initMap() {
    let world: any;
    try {
      world = await d3.json('https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json');
    } catch {
      console.error('Failed to load world map data');
      return;
    }

    const container = this.el.nativeElement.querySelector('.map-container');
    const width = container.clientWidth;
    const height = container.clientHeight;

    this.projection = d3
      .geoNaturalEarth1()
      .scale(width / 5)
      .translate([width / 2, height / 2]);

    const path = d3.geoPath().projection(this.projection);

    this.svg = d3.select(container).append('svg').attr('width', width).attr('height', height);

    this.svg.append('rect').attr('width', width).attr('height', height).attr('fill', '#0a0f1a');

    const zoomGroup = this.svg.append('g').attr('class', 'zoom-group');

    zoomGroup
      .append('g')
      .selectAll('path')
      .data((topojson.feature(world, world.objects.countries) as any).features)
      .join('path')
      .attr('d', path as unknown as string)
      .attr('fill', '#1a2540')
      .attr('stroke', '#2a3a60')
      .attr('stroke-width', 0.5);

    zoomGroup.append('g').attr('class', 'attacks');

    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([1, 8])
      .on('zoom', (event) => {
        zoomGroup.attr('transform', event.transform);
      });

    this.svg.call(zoom);
  }

  private readonly REGION_COORDS: Record<string, [number, number]> = {
    US: [-95, 38],
    EU: [10, 51],
    RU: [60, 55],
    CN: [105, 35],
    IL: [35, 31],
    BR: [-51, -14],
  };

  private drawAttack(event: ThreatEvent) {
    if (!this.svg || !this.projection) return;

    const target = this.REGION_COORDS['US'];
    const source: [number, number] = (event.lng != null && event.lat != null)
      ? [event.lng, event.lat]
      : (this.REGION_COORDS[event.region] ?? this.REGION_COORDS['EU']);
    const color = this.severityColor(event.threat_level);

    const [sx, sy] = this.projection(source)!;
    const [tx, ty] = this.projection(target)!;

    const line = this.svg
      .select('.attacks')
      .append('line')
      .attr('x1', sx)
      .attr('y1', sy)
      .attr('x2', sx)
      .attr('y2', sy)
      .attr('stroke', color)
      .attr('stroke-width', 1.5)
      .attr('opacity', 0.8);

    line
      .transition()
      .duration(800)
      .attr('x2', tx)
      .attr('y2', ty)
      .transition()
      .duration(600)
      .attr('opacity', 0)
      .remove();

    this.svg
      .select('.attacks')
      .append('circle')
      .attr('cx', tx)
      .attr('cy', ty)
      .attr('r', 0)
      .attr('fill', 'none')
      .attr('stroke', color)
      .attr('stroke-width', 1.5)
      .attr('opacity', 0.9)
      .transition()
      .delay(800)
      .duration(400)
      .attr('r', 8)
      .attr('opacity', 0)
      .remove();
  }

  private severityColor(level: string): string {
    return SEVERITY_COLORS[level] ?? SEVERITY_COLORS['low'];
  }
}
