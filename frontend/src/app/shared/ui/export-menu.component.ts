import { ChangeDetectionStrategy, Component, ElementRef, inject, output, signal } from '@angular/core';

/** "↓ Export" button with a CSV / PDF menu; closes on any click outside it. */
@Component({
  selector: 'app-export-menu',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { '(document:click)': 'onDocumentClick($event)' },
  template: `
    <button type="button" class="btn-export" [attr.aria-expanded]="open()" (click)="open.set(!open())">↓ Export</button>
    @if (open()) {
      <div class="export-dropdown">
        <button type="button" (click)="choose('csv')">CSV</button>
        <button type="button" (click)="choose('pdf')">PDF</button>
      </div>
    }
  `,
  styleUrl: './export-menu.component.scss',
})
export class ExportMenuComponent {
  readonly csv = output<void>();
  readonly pdf = output<void>();
  readonly open = signal(false);
  private readonly host = inject(ElementRef<HTMLElement>);

  choose(format: 'csv' | 'pdf') {
    this.open.set(false);
    if (format === 'csv') this.csv.emit();
    else this.pdf.emit();
  }

  onDocumentClick(e: MouseEvent) {
    if (!this.host.nativeElement.contains(e.target as Node)) this.open.set(false);
  }
}
