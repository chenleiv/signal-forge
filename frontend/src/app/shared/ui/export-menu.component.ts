import {
  ChangeDetectionStrategy, Component, DOCUMENT, DestroyRef, ElementRef, inject, output, signal, viewChild,
} from '@angular/core';

export type ExportFormat = 'csv' | 'pdf' | 'json' | 'markdown';

/**
 * "↓ Export" button with a CSV / PDF / JSON / Markdown menu; closes on any click outside it.
 *
 * The menu is position: fixed, placed from the button's viewport rect, so a
 * table container with overflow: hidden cannot clip it (a short table cut off
 * JSON and Markdown). It stays inside this element, so the tab order and the
 * outside-click check are unchanged. It follows the button on scroll and resize.
 */
@Component({
  selector: 'app-export-menu',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    '(document:click)': 'onDocumentClick($event)',
    '(window:resize)': 'reposition()',
  },
  template: `
    <button #trigger type="button" class="btn-export" [attr.aria-expanded]="open()" (click)="toggle()">↓ Export</button>
    @if (open()) {
      <div class="export-dropdown" [style.top.px]="pos().top" [style.right.px]="pos().right">
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
  /** Viewport coordinates of the menu: its top edge and its distance from the right edge. */
  readonly pos = signal({ top: 0, right: 0 });
  private readonly host = inject(ElementRef<HTMLElement>);
  private readonly doc = inject(DOCUMENT);
  private readonly trigger = viewChild.required<ElementRef<HTMLButtonElement>>('trigger');

  constructor() {
    // Scroll events do not bubble; capture catches a scroll in any container.
    const onScroll = () => this.reposition();
    this.doc.addEventListener('scroll', onScroll, { capture: true, passive: true });
    inject(DestroyRef).onDestroy(() => this.doc.removeEventListener('scroll', onScroll, { capture: true }));
  }

  toggle() {
    if (!this.open()) this.place();
    this.open.set(!this.open());
  }

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

  reposition() {
    if (this.open()) this.place();
  }

  /** Right-aligns the menu under the button, 4px below it. */
  private place() {
    const r = this.trigger().nativeElement.getBoundingClientRect();
    const viewWidth = this.doc.documentElement.clientWidth;
    this.pos.set({ top: r.bottom + 4, right: Math.max(0, viewWidth - r.right) });
  }
}
