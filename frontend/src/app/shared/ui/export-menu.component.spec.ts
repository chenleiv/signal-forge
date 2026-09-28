import { TestBed } from '@angular/core/testing';
import { ExportMenuComponent } from './export-menu.component';

describe('ExportMenuComponent', () => {
  function create() {
    const fixture = TestBed.createComponent(ExportMenuComponent);
    fixture.detectChanges();
    return fixture;
  }
  const el = (f: ReturnType<typeof create>) => f.nativeElement as HTMLElement;

  it('opens on click and emits the chosen format, then closes', () => {
    const f = create();
    const csv = vi.fn();
    const pdf = vi.fn();
    f.componentInstance.csv.subscribe(csv);
    f.componentInstance.pdf.subscribe(pdf);

    (el(f).querySelector('.btn-export') as HTMLButtonElement).click();
    f.detectChanges();
    const [csvBtn] = el(f).querySelectorAll('.export-dropdown button');
    (csvBtn as HTMLButtonElement).click();
    f.detectChanges();

    expect(csv).toHaveBeenCalledOnce();
    expect(pdf).not.toHaveBeenCalled();
    expect(el(f).querySelector('.export-dropdown')).toBeNull();
  });

  it('closes on a click outside it, not inside', () => {
    const f = create();
    f.componentInstance.open.set(true);
    f.componentInstance.onDocumentClick({ target: el(f).querySelector('.btn-export') } as unknown as MouseEvent);
    expect(f.componentInstance.open()).toBe(true);
    f.componentInstance.onDocumentClick({ target: document.body } as unknown as MouseEvent);
    expect(f.componentInstance.open()).toBe(false);
  });
});
