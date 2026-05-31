import {
  Component,
  ElementRef,
  ViewChild,
  inject,
  signal,
  OnInit,
  OnDestroy,
  AfterViewInit,
  ChangeDetectionStrategy,
  DestroyRef,
} from '@angular/core';
import { Router } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import * as d3 from 'd3';
import { ThreatStoreService } from '../../core/services/threat-store.service';
import { NetworkNode, NetworkLink } from '../../shared/models/threat.models';

interface SimNode extends d3.SimulationNodeDatum, NetworkNode {}
interface SimLink extends d3.SimulationLinkDatum<SimNode> {
  value: number;
}

@Component({
  selector: 'app-network-graph',
  standalone: true,
  templateUrl: './network-graph.component.html',
  styleUrl: './network-graph.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class NetworkGraphComponent implements OnInit, AfterViewInit, OnDestroy {
  @ViewChild('svgContainer', { static: true }) svgRef!: ElementRef<SVGElement>;

  private store      = inject(ThreatStoreService);
  private router     = inject(Router);
  private destroyRef = inject(DestroyRef);

  loading   = signal(true);
  tooltip   = signal<{ x: number; y: number; node: SimNode } | null>(null);

  private simulation?: d3.Simulation<SimNode, SimLink>;
  private resizeObserver?: ResizeObserver;

  private readonly SEVERITY_COLOR: Record<string, string> = {
    critical: '#ef4444',
    high:     '#f97316',
    medium:   '#f59e0b',
    low:      '#60a5fa',
  };

  private readonly ATTACK_COLOR: Record<string, string> = {
    SQLi:       '#a855f7',
    DDoS:       '#06b6d4',
    BruteForce: '#f97316',
    PortScan:   '#22c55e',
    Malware:    '#ef4444',
  };

  ngOnInit() {
    this.store.fetchNetwork()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: data => { this.loading.set(false); this.draw(data.nodes, data.links); },
        error: () => this.loading.set(false),
      });
  }

  ngAfterViewInit() {
    this.resizeObserver = new ResizeObserver(() => this.centerSimulation());
    this.resizeObserver.observe(this.svgRef.nativeElement.parentElement!);
  }

  ngOnDestroy() {
    this.simulation?.stop();
    this.resizeObserver?.disconnect();
  }

  private draw(rawNodes: NetworkNode[], rawLinks: NetworkLink[]) {
    const el     = this.svgRef.nativeElement as unknown as SVGSVGElement;
    const svg    = d3.select<SVGSVGElement, unknown>(el);
    const width  = (this.svgRef.nativeElement.parentElement?.clientWidth)  || 900;
    const height = (this.svgRef.nativeElement.parentElement?.clientHeight) || 600;

    svg.attr('width', width).attr('height', height);
    svg.selectAll('*').remove();

    const nodes: SimNode[] = rawNodes.map(n => ({ ...n }));
    const nodeMap = new Map(nodes.map(n => [n.id, n]));
    const links: SimLink[] = rawLinks
      .filter(l => nodeMap.has(l.source as string) && nodeMap.has(l.target as string))
      .map(l => ({ ...l, source: nodeMap.get(l.source as string)!, target: nodeMap.get(l.target as string)! }));

    // Zoom layer
    const g = svg.append('g');
    svg.call(
      d3.zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.3, 3])
        .on('zoom', e => g.attr('transform', e.transform))
    );

    // Links
    const link = g.append('g').selectAll('line')
      .data(links).join('line')
      .attr('stroke', '#2a3347')
      .attr('stroke-opacity', 0.7)
      .attr('stroke-width', d => Math.sqrt(d.value) * 0.8 + 0.5);

    // Node groups
    const node = g.append('g').selectAll<SVGGElement, SimNode>('g')
      .data(nodes).join('g')
      .attr('cursor', d => d.type === 'ip' ? 'pointer' : 'default')
      .call(
        d3.drag<SVGGElement, SimNode>()
          .on('start', (e, d) => { if (!e.active) this.simulation?.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
          .on('drag',  (e, d) => { d.fx = e.x; d.fy = e.y; })
          .on('end',   (e, d) => { if (!e.active) this.simulation?.alphaTarget(0); d.fx = null; d.fy = null; })
      );

    // IP nodes — circles
    node.filter(d => d.type === 'ip')
      .append('circle')
      .attr('r', d => Math.max(8, Math.min(22, (d.score ?? 50) / 5)))
      .attr('fill', d => this.SEVERITY_COLOR[d.threat_level ?? 'low'] + '22')
      .attr('stroke', d => this.SEVERITY_COLOR[d.threat_level ?? 'low'])
      .attr('stroke-width', 1.5);

    // Attack nodes — diamonds
    node.filter(d => d.type === 'attack')
      .append('polygon')
      .attr('points', '0,-14 12,0 0,14 -12,0')
      .attr('fill', d => this.ATTACK_COLOR[d.id] + '22')
      .attr('stroke', d => this.ATTACK_COLOR[d.id] ?? '#9ca3af')
      .attr('stroke-width', 1.5);

    // Labels
    node.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', d => d.type === 'ip' ? (Math.max(8, Math.min(22, (d.score ?? 50) / 5)) + 11) : 22)
      .attr('font-size', d => d.type === 'ip' ? '9px' : '8px')
      .attr('fill', '#9ca3af')
      .attr('pointer-events', 'none')
      .text(d => d.id);

    // Interactions
    node.filter(d => d.type === 'ip')
      .on('mouseenter', (e, d) => {
        this.tooltip.set({ x: e.offsetX + 12, y: e.offsetY - 10, node: d });
      })
      .on('mousemove', (e) => {
        this.tooltip.update(t => t ? { ...t, x: e.offsetX + 12, y: e.offsetY - 10 } : t);
      })
      .on('mouseleave', () => this.tooltip.set(null))
      .on('click', (_, d) => {
        this.router.navigate(['/threats'], { queryParams: { ip: d.id } });
      });

    // Simulation
    this.simulation = d3.forceSimulation<SimNode>(nodes)
      .force('link',   d3.forceLink<SimNode, SimLink>(links).id(d => d.id).distance(90))
      .force('charge', d3.forceManyBody().strength(-220))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collide', d3.forceCollide(30))
      .on('tick', () => {
        link
          .attr('x1', d => (d.source as SimNode).x ?? 0)
          .attr('y1', d => (d.source as SimNode).y ?? 0)
          .attr('x2', d => (d.target as SimNode).x ?? 0)
          .attr('y2', d => (d.target as SimNode).y ?? 0);
        node.attr('transform', d => `translate(${d.x ?? 0},${d.y ?? 0})`);
      });
  }

  private centerSimulation() {
    const el = this.svgRef.nativeElement as SVGElement;
    const w  = el.parentElement?.clientWidth  ?? 900;
    const h  = el.parentElement?.clientHeight ?? 600;
    el.setAttribute('width',  String(w));
    el.setAttribute('height', String(h));
    this.simulation?.force('center', d3.forceCenter(w / 2, h / 2)).alpha(0.3).restart();
  }
}
