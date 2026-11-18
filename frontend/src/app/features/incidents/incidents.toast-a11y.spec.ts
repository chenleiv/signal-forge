import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';
import { Incidents } from './incidents';
import { ThreatStoreService } from '../../core/services/threat-store.service';
import { AuthService } from '../../core/services/auth';

/** The toast sits in a polite live region that exists before any message, so it is announced. */
describe('Incidents: the toast is announced to screen readers', () => {
  function open() {
    TestBed.configureTestingModule({
      imports: [Incidents],
      providers: [
        provideRouter([]),
        { provide: ThreatStoreService, useValue: {
          fetchIncidents: () => of([]), getUsers: () => of([]), getUserDirectory: () => of([]),
        } },
        { provide: AuthService, useValue: { currentUser: signal(null) } },
      ],
    });
    const fixture = TestBed.createComponent(Incidents);
    fixture.detectChanges();
    return fixture;
  }

  it('the live region is present while empty and holds the message once shown', () => {
    vi.useFakeTimers();
    try {
      const f = open();
      const region = f.nativeElement.querySelector('.toast-region') as HTMLElement;
      expect(region.getAttribute('role')).toBe('status');
      expect(region.getAttribute('aria-live')).toBe('polite');
      expect(region.getAttribute('aria-atomic')).toBe('true');
      expect(region.querySelector('.toast')).toBeNull();

      f.componentInstance.showToast('Case INC-1 already exists — opened existing');
      f.detectChanges();

      expect(f.nativeElement.querySelector('.toast-region')).toBe(region);  // same node, not re-created
      expect(region.querySelector('.toast')?.textContent?.trim()).toBe('Case INC-1 already exists — opened existing');
    } finally {
      vi.useRealTimers();
    }
  });
});
