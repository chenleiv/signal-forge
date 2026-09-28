import { TestBed } from '@angular/core/testing';
import { FilterPillsComponent } from './filter-pills.component';

describe('FilterPillsComponent', () => {
  function create(value = 'all') {
    const fixture = TestBed.createComponent(FilterPillsComponent);
    fixture.componentRef.setInput('options', ['critical', 'high']);
    fixture.componentRef.setInput('allLabel', 'All Sev');
    fixture.componentRef.setInput('value', value);
    fixture.detectChanges();
    return fixture;
  }
  const pills = (f: ReturnType<typeof create>) =>
    [...(f.nativeElement as HTMLElement).querySelectorAll('button')] as HTMLButtonElement[];

  it('shows "all" first, then each option', () => {
    expect(pills(create()).map(b => b.textContent?.trim())).toEqual(['All Sev', 'critical', 'high']);
  });

  it('marks the current value as pressed and updates it on click', () => {
    const f = create('high');
    expect(pills(f).map(b => b.getAttribute('aria-pressed'))).toEqual(['false', 'false', 'true']);

    pills(f)[1].click();
    f.detectChanges();

    expect(f.componentInstance.value()).toBe('critical');
    expect(pills(f)[1].classList).toContain('active');
  });
});
