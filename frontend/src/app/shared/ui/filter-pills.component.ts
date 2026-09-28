import { ChangeDetectionStrategy, Component, input, model } from '@angular/core';

/**
 * One-of-many filter buttons ("All", then each option). Two-way bound:
 * <app-filter-pills [options]="..." allLabel="All Sev" [(value)]="severity" />
 * Each option gets a pill-<option> class for its color (statuses, severities).
 */
@Component({
  selector: 'app-filter-pills',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @for (option of ['all', ...options()]; track option) {
      <button type="button" class="pill pill-{{ option }}" [class.active]="value() === option"
              [attr.aria-pressed]="value() === option" (click)="value.set(option)">
        {{ option === 'all' ? allLabel() : option }}
      </button>
    }
  `,
  styleUrl: './filter-pills.component.scss',
})
export class FilterPillsComponent {
  readonly options = input.required<readonly string[]>();
  readonly allLabel = input('All');
  readonly value = model('all');
}
