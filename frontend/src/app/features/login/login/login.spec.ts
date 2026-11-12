import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { Router } from '@angular/router';
import { of, throwError } from 'rxjs';
import { Login } from './login';
import { AuthService } from '../../../core/services/auth';
import { DemoModeService } from '../../../core/services/demo-mode.service';

const USER = { username: 'analyst', display_name: 'Tier 1 Analyst', role: 'analyst' as const };
const LOGIN_URL = 'http://localhost/auth/login';
const ME_URL = 'http://localhost/auth/me';

describe('Login', () => {
  const demoEnabled = signal(false);
  const auth = {
    login: vi.fn(() => of(USER)),
    ping: vi.fn(() => of(void 0)),
  };
  const router = { navigate: vi.fn() };

  function create() {
    TestBed.configureTestingModule({
      imports: [Login],
      providers: [
        { provide: AuthService, useValue: auth },
        { provide: Router, useValue: router },
        { provide: DemoModeService, useValue: { enabled: demoEnabled, load: vi.fn() } },
      ],
    });
    const fixture = TestBed.createComponent(Login);
    fixture.detectChanges();
    return { fixture, el: fixture.nativeElement as HTMLElement };
  }

  function failWith(status: number, url = LOGIN_URL) {
    auth.login.mockReturnValueOnce(throwError(() => new HttpErrorResponse({ status, url })));
    const { fixture, el } = create();
    fixture.componentInstance.username.set('someone');
    fixture.componentInstance.password.set('some-password');
    fixture.componentInstance.submit();
    fixture.detectChanges();
    return { fixture, alert: el.querySelector('[role=alert]')?.textContent ?? '' };
  }

  const demoButton = (el: HTMLElement, label: string) =>
    [...el.querySelectorAll<HTMLButtonElement>('.demo-btn')].find(b => b.textContent?.includes(label));

  beforeEach(() => { vi.clearAllMocks(); demoEnabled.set(false); });

  describe('failure messages', () => {
    it('says the credentials are wrong on a 401 from the login call', () => {
      expect(failWith(401).alert).toContain('Invalid username or password');
    });

    it('asks the user to wait on a 429, without promising when it ends', () => {
      const { alert } = failWith(429);
      expect(alert).toContain('Too many attempts');
      expect(alert).not.toContain('minute');
    });

    it.each([0, 502, 503, 504])('says the server is unreachable on status %i', status => {
      const { alert } = failWith(status);
      expect(alert).toContain('waking up or unreachable');
      expect(alert).not.toContain('Invalid');
    });

    it('does not blame the credentials on a server error', () => {
      const { alert } = failWith(500);
      expect(alert).toContain('Something went wrong');
      expect(alert).not.toContain('Invalid');
    });

    it('does not blame the credentials when /auth/me fails after a successful login', () => {
      const { alert } = failWith(401, ME_URL);
      expect(alert).toContain('Something went wrong');
      expect(alert).not.toContain('Invalid');
    });

    it.each([401, 429, 0, 503, 500])('can retry after status %i', status => {
      const { fixture } = failWith(status);
      const c = fixture.componentInstance;
      expect(c.loading()).toBe(false);

      c.submit();
      expect(router.navigate).toHaveBeenCalledWith(['/dashboard']);
      expect(c.error()).toBeNull();
    });
  });

  describe('page content', () => {
    it('shows the demo buttons before the form in demo mode', () => {
      demoEnabled.set(true);
      const { el } = create();
      const button = demoButton(el, 'Try as Admin');
      const form = el.querySelector('form');

      expect(button).toBeTruthy();
      expect(button!.compareDocumentPosition(form!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    });

    it('hides the demo section outside demo mode', () => {
      const { el } = create();
      expect(el.querySelector('.demo-btn')).toBeNull();
      expect(el.querySelector('.login-or')).toBeNull();
    });

    it.each([true, false])('explains the product when demo mode is %s', enabled => {
      demoEnabled.set(enabled);
      const { el } = create();
      expect(el.querySelector('.login-sub')?.textContent).toContain('SOC dashboard');
    });

    it('signs in with the account of the demo button that was clicked', () => {
      demoEnabled.set(true);
      const { el } = create();
      demoButton(el, 'Try as Analyst')!.click();
      expect(auth.login).toHaveBeenCalledWith('analyst', 'analyst-demo');
    });
  });
});
