import { TestBed } from '@angular/core/testing';
import { ExportMenuComponent } from './export-menu.component';

describe('ExportMenuComponent: formats', () => {
  function openMenu() {
    const fixture = TestBed.createComponent(ExportMenuComponent);
    fixture.detectChanges();
    (fixture.nativeElement.querySelector('.btn-export') as HTMLButtonElement).click();
    fixture.detectChanges();
    return fixture;
  }
  const buttons = (f: ReturnType<typeof openMenu>) =>
    Array.from((f.nativeElement as HTMLElement).querySelectorAll<HTMLButtonElement>('.export-dropdown button'));

  it('lists CSV, PDF, JSON and Markdown, in that order', () => {
    expect(buttons(openMenu()).map(b => b.textContent?.trim())).toEqual(['CSV', 'PDF', 'JSON', 'Markdown']);
  });

  it.each([
    ['CSV', 'csv'],
    ['PDF', 'pdf'],
    ['JSON', 'json'],
    ['Markdown', 'markdown'],
  ] as const)('%s emits only its own output and closes the menu', (label, name) => {
    const f = openMenu();
    const menu = f.componentInstance;
    const spies = {
      csv: vi.fn(), pdf: vi.fn(), json: vi.fn(), markdown: vi.fn(),
    };
    menu.csv.subscribe(spies.csv);
    menu.pdf.subscribe(spies.pdf);
    menu.json.subscribe(spies.json);
    menu.markdown.subscribe(spies.markdown);

    buttons(f).find(b => b.textContent?.trim() === label)!.click();
    f.detectChanges();

    for (const [key, spy] of Object.entries(spies)) {
      if (key === name) expect(spy).toHaveBeenCalledOnce();
      else expect(spy).not.toHaveBeenCalled();
    }
    expect(f.nativeElement.querySelector('.export-dropdown')).toBeNull();
  });

  it('every menu item is a type="button" element', () => {
    for (const b of buttons(openMenu())) expect(b.getAttribute('type')).toBe('button');
  });
});
