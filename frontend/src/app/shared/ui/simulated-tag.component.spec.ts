import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';

import { DemoModeService } from '../../core/services/demo-mode.service';
import { feedNotice } from '../../core/services/threat-feed.service';
import { SIMULATED_TAG_LABEL, SimulatedTagComponent } from './simulated-tag.component';

describe('SimulatedTagComponent', () => {
  function create(demo: boolean) {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    TestBed.inject(DemoModeService).enabled.set(demo);
    const fixture = TestBed.createComponent(SimulatedTagComponent);
    fixture.detectChanges();
    return (fixture.nativeElement as HTMLElement).querySelector<HTMLElement>('.sim-tag');
  }

  it('shows a visible "Simulated" note with a name for screen readers in demo mode', () => {
    const tag = create(true);
    expect(tag).not.toBeNull();
    expect(tag!.textContent?.trim()).toBe('Simulated');
    expect(tag!.getAttribute('role')).toBe('note');
    expect(tag!.getAttribute('aria-label')).toBe(SIMULATED_TAG_LABEL);
    // Label in name (WCAG 2.5.3): the accessible name starts with the visible text.
    expect(SIMULATED_TAG_LABEL.startsWith('Simulated')).toBe(true);
  });

  it('renders nothing outside demo mode', () => {
    expect(create(false)).toBeNull();
  });
});

describe('feedNotice for the simulated demo feed', () => {
  it('shows no feed banner: the demo banner and the tags explain it', () => {
    expect(feedNotice({ state: 'simulated', reason: null })).toBeNull();
  });
});
