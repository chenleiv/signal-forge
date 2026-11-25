import { ChangeDetectionStrategy, Component, ElementRef, inject, output, signal } from '@angular/core';

export type ExportFormat = 'csv' | 'pdf' | 'json' | 'markdown';

/** "↓ Export" button with a CSV / PDF / JSON / Markdown menu; closes on any click outside it. */
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
        <button type="button" (click)="choose('json')">JSON</button>
        <button type="button" (click)="choose('markdown')">Markdown</button>
      </div>
    }
  `,
  styleUrl: './export-menu.component.scss',
})
export class ExportMenuComponent {
  readonly csv = output<void>();
  readonly pdf = output<void>();
  readonly json = output<void>();
  readonly markdown = output<void>();
  readonly open = signal(false);
  private readonly host = inject(ElementRef<HTMLElement>);

  choose(format: ExportFormat) {
    this.open.set(false);
    switch (format) {
      case 'csv': this.csv.emit(); break;
      case 'pdf': this.pdf.emit(); break;
      case 'json': this.json.emit(); break;
      case 'markdown': this.markdown.emit(); break;
    }
  }

  onDocumentClick(e: MouseEvent) {
    if (!this.host.nativeElement.contains(e.target as Node)) this.open.set(false);
  }
}
