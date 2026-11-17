import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { of } from 'rxjs';
import { RulesComponent } from './rules.component';
import { ThreatStoreService } from '../../core/services/threat-store.service';
import { AuthService } from '../../core/services/auth';
import { CurrentUser } from '../../core/auth/permissions';
import { DetectionRule } from '../../shared/models/threat.models';

const RULE = {
  id: 'r1', name: 'High score', enabled: true, logic: 'AND',
  conditions: [{ field: 'score', operator: '>', value: 75 }], actions: ['alert'],
  match_count: 0, created_at: '2026-09-26T10:00:00Z',
} as DetectionRule;

describe('RulesComponent: icon buttons have accessible names', () => {
  const user = signal<CurrentUser>({ username: 'admin', display_name: 'Sarah Kim', role: 'admin' });

  function create(rule: DetectionRule) {
    TestBed.configureTestingModule({
      imports: [RulesComponent],
      providers: [
        { provide: ThreatStoreService, useValue: {
          getRules: () => of([rule]), createRule: () => of(rule),
          updateRule: () => of(rule), deleteRule: () => of(void 0),
        } },
        { provide: AuthService, useValue: { currentUser: user } },
      ],
    });
    const fixture = TestBed.createComponent(RulesComponent);
    fixture.detectChanges();
    return fixture;
  }

  it('the enable toggle is a named toggle button that reports its state', () => {
    const el = create(RULE).nativeElement as HTMLElement;
    const toggle = el.querySelector('.rule-toggle')!;
    expect(toggle.getAttribute('aria-label')).toBe('Rule High score enabled');
    expect(toggle.getAttribute('aria-pressed')).toBe('true');
  });

  it('a disabled rule reports aria-pressed false', () => {
    const el = create({ ...RULE, enabled: false }).nativeElement as HTMLElement;
    expect(el.querySelector('.rule-toggle')!.getAttribute('aria-pressed')).toBe('false');
  });

  it('the delete rule and remove condition buttons are named', () => {
    const fixture = create(RULE);
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('.rule-del')!.getAttribute('aria-label')).toBe('Delete rule High score');

    fixture.componentInstance.selectRule(RULE);
    fixture.detectChanges();
    expect(el.querySelector('.cond-del')!.getAttribute('aria-label')).toBe('Remove condition 1');
  });
});
