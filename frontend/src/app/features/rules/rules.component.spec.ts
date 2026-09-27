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

describe('RulesComponent: analysts are read-only', () => {
  const store = {
    getRules: vi.fn(() => of([RULE])),
    createRule: vi.fn(() => of(RULE)),
    updateRule: vi.fn(() => of(RULE)),
    deleteRule: vi.fn(() => of(void 0)),
  };
  const user = signal<CurrentUser>({ username: 'alice', display_name: 'Alice Chen', role: 'analyst' });

  function create() {
    TestBed.configureTestingModule({
      imports: [RulesComponent],
      providers: [
        { provide: ThreatStoreService, useValue: store },
        { provide: AuthService, useValue: { currentUser: user } },
      ],
    });
    const fixture = TestBed.createComponent(RulesComponent);
    fixture.detectChanges();
    return fixture;
  }

  beforeEach(() => vi.clearAllMocks());

  it('clicking the (aria-disabled) enable toggle sends nothing', () => {
    const fixture = create();
    const toggle = fixture.nativeElement.querySelector('.rule-toggle') as HTMLButtonElement;
    expect(toggle.getAttribute('aria-disabled')).toBe('true');
    expect(toggle.title).toBe('Admin role required');

    toggle.click();

    expect(store.updateRule).not.toHaveBeenCalled();
  });

  it('write handlers do nothing for an analyst', () => {
    const c = create().componentInstance;
    const e = new Event('click');
    c.newRule();
    expect(c.isNew()).toBe(false);  // the editor did not open for a new rule
    c.selectRule(RULE);
    c.save();
    c.deleteRule(RULE, e);
    expect(c.isNew()).toBe(false);
    expect(store.createRule).not.toHaveBeenCalled();
    expect(store.updateRule).not.toHaveBeenCalled();
    expect(store.deleteRule).not.toHaveBeenCalled();
  });

  it('hides New/delete/save and shows a read-only notice', () => {
    const fixture = create();
    fixture.componentInstance.selectRule(RULE);
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('.btn-new')).toBeNull();
    expect(el.querySelector('.rule-del')).toBeNull();
    expect(el.querySelector('.btn-save')).toBeNull();
    expect(el.querySelector('.readonly-banner')?.textContent).toContain('Only admins');
    expect((el.querySelector('.editor-fieldset') as HTMLFieldSetElement).disabled).toBe(true);
  });

  it('admins can toggle', () => {
    user.set({ username: 'admin', display_name: 'Sarah Kim', role: 'admin' });
    const fixture = create();
    (fixture.nativeElement.querySelector('.rule-toggle') as HTMLButtonElement).click();
    expect(store.updateRule).toHaveBeenCalledOnce();
    user.set({ username: 'alice', display_name: 'Alice Chen', role: 'analyst' });
  });

  it('closeEditor returns to the list without writing anything', () => {
    const c = create().componentInstance;
    c.selectRule(RULE);
    c.closeEditor();
    expect(c.selected()).toBeNull();
    expect(c.isNew()).toBe(false);
    expect(store.updateRule).not.toHaveBeenCalled();
  });
});
