import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';
import { ThreatHuntingComponent } from './threat-hunting.component';
import { ThreatStoreService } from '../../core/services/threat-store.service';
import { HuntResult, SavedHunt } from '../../shared/models/threat.models';

const SAVED: SavedHunt[] = [
  { id: 'h1', name: 'Russian scans', query: { region: 'RU' }, created_at: '2026-11-16T10:00:00Z', result_count: 4 },
];
const RESULTS: HuntResult[] = [
  { ip: '185.220.101.34', score: 91, threat_level: 'critical', attack_type: 'BruteForce',
    region: 'RU', timestamp: '2026-11-16T10:00:00Z' },
];

describe('ThreatHuntingComponent: icon buttons have accessible names', () => {
  function create() {
    TestBed.configureTestingModule({
      imports: [ThreatHuntingComponent],
      providers: [
        provideRouter([]),
        { provide: ThreatStoreService, useValue: {
          getSavedHunts: () => of(SAVED),
          runHunt: () => of({ results: RESULTS, total: RESULTS.length }),
          saveHunt: () => of(SAVED[0]),
          deleteHunt: () => of(void 0),
        } },
      ],
    });
    const fixture = TestBed.createComponent(ThreatHuntingComponent);
    fixture.detectChanges();
    return fixture;
  }

  it('the saved hunt delete button is named after the hunt', () => {
    const el = create().nativeElement as HTMLElement;
    expect(el.querySelector('.saved-del')!.getAttribute('aria-label')).toBe('Delete saved hunt Russian scans');
  });

  it('the investigate button is named after the IP, and the save cancel button is named', () => {
    const fixture = create();
    fixture.componentInstance.run();
    fixture.componentInstance.showSave.set(true);
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('.investigate-btn')!.getAttribute('aria-label')).toBe('Investigate 185.220.101.34');
    expect(el.querySelector('.save-row .btn-clear')!.getAttribute('aria-label')).toBe('Cancel saving the hunt');
  });
});
