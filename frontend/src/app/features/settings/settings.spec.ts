import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { of, throwError } from 'rxjs';
import { Settings } from './settings';
import { AuthService } from '../../core/services/auth';
import { DemoModeService } from '../../core/services/demo-mode.service';

const ALICE = { username: 'alice', display_name: 'Alice Chen', role: 'analyst' as const };
const CURRENT = 'my-current-password';
const NEXT = 'a-brand-new-password-9';

describe('Settings: change password', () => {
  const demo = signal(false);
  const auth = {
    currentUser: signal(ALICE),
    changePassword: vi.fn(() => of(ALICE)),
    logout: vi.fn(),
  };

  function create() {
    TestBed.configureTestingModule({
      imports: [Settings],
      providers: [
        { provide: AuthService, useValue: auth },
        { provide: DemoModeService, useValue: { enabled: demo } },
      ],
    });
    const fixture = TestBed.createComponent(Settings);
    fixture.detectChanges();
    return fixture;
  }

  const fill = (c: Settings, current: string, next: string, confirm = next) => {
    c.currentPw.set(current); c.newPw.set(next); c.confirmPw.set(confirm);
  };

  beforeEach(() => { vi.clearAllMocks(); demo.set(false); });

  it('changes the password, clears the fields and says other sessions were signed out', () => {
    const fixture = create();
    const c = fixture.componentInstance;
    fill(c, CURRENT, NEXT);
    c.changePassword();
    fixture.detectChanges();

    expect(auth.changePassword).toHaveBeenCalledWith(CURRENT, NEXT);
    expect([c.currentPw(), c.newPw(), c.confirmPw()]).toEqual(['', '', '']);
    expect((fixture.nativeElement as HTMLElement).querySelector('[role=status]')?.textContent)
      .toContain('other sessions were signed out');
  });

  it.each([
    ['too short', CURRENT, 'short', 'short', '12-72 characters'],
    ['too long', CURRENT, 'x'.repeat(73), 'x'.repeat(73), '12-72 characters'],
    ['same as current', CURRENT, CURRENT, CURRENT, 'different from the current one'],
    ['repeat does not match', CURRENT, NEXT, NEXT + '!', 'do not match'],
  ])('%s: explains why and sends nothing', (_name, current, next, confirm, message) => {
    const fixture = create();
    const c = fixture.componentInstance;
    fill(c, current, next, confirm);
    fixture.detectChanges();

    expect(c.pwProblem()).toContain(message);
    expect((fixture.nativeElement as HTMLElement).querySelector('[role=alert]')?.textContent).toContain(message);
    expect(c.canSubmitPw()).toBe(false);
    c.changePassword();   // called directly: still refused
    expect(auth.changePassword).not.toHaveBeenCalled();
  });

  it('the repeated new password is required', () => {
    const c = create().componentInstance;
    fill(c, CURRENT, NEXT, '');
    expect(c.canSubmitPw()).toBe(false);
    c.changePassword();
    expect(auth.changePassword).not.toHaveBeenCalled();
  });

  it('counts bytes, not characters (the server limit is 72 bytes)', () => {
    const c = create().componentInstance;
    fill(c, CURRENT, 'é'.repeat(37));   // 37 characters, 74 bytes
    expect(c.pwProblem()).toContain('12-72 characters');
  });

  it('shows the server reason when it refuses', () => {
    auth.changePassword.mockReturnValueOnce(throwError(() => new HttpErrorResponse({
      status: 403, error: { detail: 'Current password is incorrect' } })));
    const fixture = create();
    const c = fixture.componentInstance;
    fill(c, 'wrong-password-1', NEXT);
    c.changePassword();
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).querySelector('[role=alert]')?.textContent)
      .toContain('Current password is incorrect');
    expect(c.currentPw()).toBe('wrong-password-1');   // not cleared on failure
  });

  it('rate limited: a plain message', () => {
    auth.changePassword.mockReturnValueOnce(throwError(() => new HttpErrorResponse({ status: 429 })));
    const c = create().componentInstance;
    fill(c, CURRENT, NEXT);
    c.changePassword();
    expect(c.pwError()).toContain('Too many attempts');
  });

  describe('demo mode', () => {
    beforeEach(() => demo.set(true));

    it('the form is locked with an explanation, and the handler refuses too', () => {
      const fixture = create();
      const el = fixture.nativeElement as HTMLElement;
      expect(el.textContent).toContain('Password changes are off in the public demo');
      expect((el.querySelector('#current-password') as HTMLInputElement).disabled).toBe(true);

      const c = fixture.componentInstance;
      fill(c, CURRENT, NEXT);
      c.changePassword();
      expect(auth.changePassword).not.toHaveBeenCalled();
    });
  });
});
