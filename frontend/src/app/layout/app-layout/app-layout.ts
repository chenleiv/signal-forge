import { Component, OnInit, OnDestroy, signal, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { ThreatsService } from '../../core/services/threats.service';

@Component({
  selector: 'app-layout',
  standalone: true,
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  templateUrl: './app-layout.html',
  styleUrl: './app-layout.scss',
})
export class AppLayout implements OnInit, OnDestroy {
  private ws = inject(ThreatsService);

  time = signal('');

  private timer: ReturnType<typeof setInterval> | null = null;

  ngOnInit() {
    this.tick();
    this.timer = setInterval(() => this.tick(), 1000);
    this.ws.connect();
  }

  ngOnDestroy() {
    if (this.timer) clearInterval(this.timer);
    this.ws.disconnect();
  }

  private tick() {
    this.time.set(new Date().toLocaleTimeString('he-IL', { hour12: false }));
  }
}
