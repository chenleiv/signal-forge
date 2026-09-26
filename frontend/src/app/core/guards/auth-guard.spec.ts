import { TestBed } from '@angular/core/testing';
import { ActivatedRouteSnapshot, CanActivateFn, Router, RouterStateSnapshot, UrlTree, provideRouter } from '@angular/router';
import { Observable, firstValueFrom, isObservable, of } from 'rxjs';
import { signal } from '@angular/core';

import { authGuard } from './auth-guard';
import { AuthService } from '../services/auth';

describe('authGuard', () => {
  const authenticated = signal(false);
  const auth = { isAuthenticated: authenticated, checkAuth: vi.fn<() => Observable<boolean>>() };

  const run: CanActivateFn = (...args) => TestBed.runInInjectionContext(() => authGuard(...args));
  const activate = async () => {
    const r = run({} as ActivatedRouteSnapshot, {} as RouterStateSnapshot);
    return isObservable(r) ? firstValueFrom(r) : r;
  };

  beforeEach(() => {
    authenticated.set(false);
    auth.checkAuth.mockReset();
    TestBed.configureTestingModule({
      providers: [provideRouter([]), { provide: AuthService, useValue: auth }],
    });
  });

  it('lets an authenticated user through without a server round trip', async () => {
    authenticated.set(true);
    expect(await activate()).toBe(true);
    expect(auth.checkAuth).not.toHaveBeenCalled();
  });

  it('lets a user with a valid session cookie through (e.g. after a page reload)', async () => {
    auth.checkAuth.mockReturnValue(of(true));
    expect(await activate()).toBe(true);
  });

  it('redirects to /login when not authenticated', async () => {
    auth.checkAuth.mockReturnValue(of(false));
    const result = await activate();
    expect(result).toBeInstanceOf(UrlTree);
    expect(TestBed.inject(Router).serializeUrl(result as UrlTree)).toBe('/login');
  });
});
