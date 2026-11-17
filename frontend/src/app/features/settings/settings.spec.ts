import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { of, throwError } from 'rxjs';
import { Settings } from './settings';
import { AuthService } from '../../core/services/auth';
import { DemoModeService } from '../../core/services/demo-mode.service';
import { SettingsService } from '../../core/services/settings.service';

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

  describe('collapsible form', () => {
    const details = (f: ReturnType<typeof create>) =>
      (f.nativeElement as HTMLElement).querySelector('details.pw-details') as HTMLDetailsElement;
    const summary = (f: ReturnType<typeof create>) => details(f).querySelector('summary') as HTMLElement;
    const currentInput = (f: ReturnType<typeof create>) =>
      (f.nativeElement as HTMLElement).querySelector('#current-password') as HTMLInputElement;
    // The toggle event is queued by the browser after the open state changes.
    const nextToggle = (f: ReturnType<typeof create>) =>
      new Promise<void>(resolve => details(f).addEventListener('toggle', () => resolve(), { once: true }));

    it('is closed by default, with the form still in the DOM', () => {
      const f = create();
      expect(details(f).open).toBe(false);
      expect(f.componentInstance.pwOpen()).toBe(false);
      expect(currentInput(f)).not.toBeNull();
    });

    it('the control is a native summary, the first child of the details element (Enter and Space work natively)', () => {
      const f = create();
      expect(details(f).firstElementChild).toBe(summary(f));
      expect(summary(f).textContent).toContain('Change Password');
    });

    it('the signal follows the native toggle: opening focuses the current password', async () => {
      const f = create();
      const toggled = nextToggle(f);
      summary(f).click();
      await toggled;
      f.detectChanges();
      expect(details(f).open).toBe(true);
      expect(f.componentInstance.pwOpen()).toBe(true);
      expect(document.activeElement).toBe(currentInput(f));
    });

    it('the signal follows the native toggle: closing clears the fields and the error', async () => {
      const f = create();
      const c = f.componentInstance;
      let toggled = nextToggle(f);
      summary(f).click();
      await toggled;
      fill(c, CURRENT, 'short', 'short');
      c.pwError.set('Current password is incorrect');

      toggled = nextToggle(f);
      summary(f).click();
      await toggled;
      f.detectChanges();
      expect(details(f).open).toBe(false);
      expect(c.pwOpen()).toBe(false);
      expect([c.currentPw(), c.newPw(), c.confirmPw()]).toEqual(['', '', '']);
      expect(c.pwError()).toBeNull();
    });

    it('setPwOpen changes the element, and its toggle event keeps the signal in step', async () => {
      const f = create();
      const c = f.componentInstance;
      let toggled = nextToggle(f);
      c.setPwOpen(true);
      await toggled;
      expect([details(f).open, c.pwOpen()]).toEqual([true, true]);

      toggled = nextToggle(f);
      c.setPwOpen(false);
      await toggled;
      expect([details(f).open, c.pwOpen()]).toEqual([false, false]);
    });

    it('closes after a successful change, keeps the message visible and focuses the summary', async () => {
      const f = create();
      const c = f.componentInstance;
      const toggled = nextToggle(f);
      summary(f).click();
      await toggled;
      fill(c, CURRENT, NEXT);
      c.changePassword();
      f.detectChanges();
      await f.whenStable();

      expect(c.pwOpen()).toBe(false);
      expect(details(f).open).toBe(false);
      const status = (f.nativeElement as HTMLElement).querySelector('[role=status]') as HTMLElement;
      expect(status.textContent).toContain('other sessions were signed out');
      expect(details(f).contains(status)).toBe(false);   // outside the closed details, so visible
      expect(document.activeElement).toBe(summary(f));
    });

    it('stays open with the server error visible when the change is refused', async () => {
      auth.changePassword.mockReturnValueOnce(throwError(() => new HttpErrorResponse({
        status: 403, error: { detail: 'Current password is incorrect' } })));
      const f = create();
      const c = f.componentInstance;
      const toggled = nextToggle(f);
      summary(f).click();
      await toggled;
      fill(c, 'wrong-password-1', NEXT);
      c.changePassword();
      f.detectChanges();
      await f.whenStable();

      expect(c.pwOpen()).toBe(true);
      expect(details(f).open).toBe(true);
      const alert = details(f).querySelector('[role=alert]');
      expect(alert?.textContent).toContain('Current password is incorrect');
    });

    it('demo mode: the note shows while closed, and opening does not focus a disabled field', async () => {
      demo.set(true);
      const f = create();
      const note = (f.nativeElement as HTMLElement).querySelector('.card-note') as HTMLElement;
      expect(note.textContent).toContain('Password changes are off');
      expect(details(f).contains(note)).toBe(false);

      const toggled = nextToggle(f);
      summary(f).click();
      await toggled;
      expect(f.componentInstance.pwOpen()).toBe(true);
      expect(document.activeElement).not.toBe(currentInput(f));
    });
  });

  describe('every card is collapsible', () => {
    const cards = (f: ReturnType<typeof create>) =>
      [...(f.nativeElement as HTMLElement).querySelectorAll('section.card')] as HTMLElement[];
    const detailsOf = (card: HTMLElement) => card.querySelector('details.card-details') as HTMLDetailsElement;

    it('each card is a details element with its summary first, and every card starts closed', () => {
      const f = create();
      const state = cards(f).map(card => {
        const details = detailsOf(card);
        const summary = details.firstElementChild as HTMLElement;
        expect(summary.tagName).toBe('SUMMARY');
        return [summary.querySelector('.card-title')?.textContent?.trim(), details.open];
      });
      expect(state).toEqual([
        ['User Profile', false],
        ['Change Password', false],
        ['Appearance', false],
        ['Connection', false],
        ['Alert Thresholds', false],
      ]);
    });

    it('closing a settings card keeps unsaved edits, and Save still stores them', async () => {
      const f = create();
      const c = f.componentInstance;
      const save = vi.spyOn(TestBed.inject(SettingsService), 'save').mockImplementation(() => undefined);
      const el = f.nativeElement as HTMLElement;
      const url = el.querySelector('#ws-url') as HTMLInputElement;
      url.value = 'wss://soc.example/ws/threats';
      url.dispatchEvent(new Event('input'));

      const connection = detailsOf(url.closest('section.card') as HTMLElement);
      connection.open = false;
      connection.dispatchEvent(new Event('toggle'));
      f.detectChanges();
      expect(connection.open).toBe(false);
      expect(c.form().wsUrl).toBe('wss://soc.example/ws/threats');
      expect(url.value).toBe('wss://soc.example/ws/threats');

      c.save();
      expect(save).toHaveBeenCalledWith(expect.objectContaining({ wsUrl: 'wss://soc.example/ws/threats' }));
    });
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
