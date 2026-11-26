import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { DemoModeService } from '../../core/services/demo-mode.service';

export const SIMULATED_TAG_LABEL = 'Simulated data: these IP addresses are not real hosts';

/**
 * Small "Simulated" tag next to data built from the demo feed. Shown only in
 * demo mode, where every IP address comes from the reserved documentation
 * ranges (192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24). The accessible name
 * starts with the visible text, so voice control can target it.
 */
@Component({
  selector: 'app-simulated-tag',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (demo.enabled()) {
      <span class="sim-tag" role="note" [attr.aria-label]="label" [attr.title]="label">Simulated</span>
    }
  `,
  styleUrl: './simulated-tag.component.scss',
})
export class SimulatedTagComponent {
  protected readonly demo = inject(DemoModeService);
  protected readonly label = SIMULATED_TAG_LABEL;
}
