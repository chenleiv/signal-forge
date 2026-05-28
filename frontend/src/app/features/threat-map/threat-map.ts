import { Component, signal } from '@angular/core';
import { interval } from 'rxjs';

type ThreatNode = {
  id: number;
  region: 'us' | 'eu' | 'ru' | 'il';
  severity: 'low' | 'medium' | 'high' | 'critical';
};

@Component({
  selector: 'app-threat-map',
  standalone: true,
  templateUrl: './threat-map.html',
  styleUrl: './threat-map.scss',
})
export class ThreatMap {
  threats = signal<ThreatNode[]>([]);

  private idCounter = 0;

  constructor() {
    this.startSimulation();
  }

  startSimulation() {
    interval(1500).subscribe(() => {
      this.addThreat();
      this.cleanupThreats();
    });
  }

  addThreat() {
    const regions: ThreatNode['region'][] = ['us', 'eu', 'ru', 'il'];
    const severities: ThreatNode['severity'][] = ['low', 'medium', 'high', 'critical'];

    const newThreat: ThreatNode = {
      id: this.idCounter++,
      region: regions[Math.floor(Math.random() * regions.length)],
      severity: severities[Math.floor(Math.random() * severities.length)],
    };

    this.threats.update((list) => [...list, newThreat]);
  }

  cleanupThreats() {
    this.threats.update((list) => list.slice(-15));
  }

  getColor(severity: ThreatNode['severity']) {
    switch (severity) {
      case 'low':
        return '#38bdf8';
      case 'medium':
        return '#fbbf24';
      case 'high':
        return '#fb923c';
      case 'critical':
        return '#ef4444';
    }
  }
}
