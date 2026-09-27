import { TestBed } from '@angular/core/testing';
import { ActivatedRouteSnapshot, CanActivateFn, Router, RouterStateSnapshot, UrlTree, provideRouter } from '@angular/router';
import { Observable, firstValueFrom, isObservable, of } from 'rxjs';
import { signal } from '@angular/core';

import { adminGuard } from './admin-guard';
import { AuthService } from '../services/auth';
import { CurrentUser } from '../auth/permissions';

describe('adminGuard', () => {
  const user = signal<CurrentUser | null>(null);
  const auth = { currentUser: user, checkAuth: vi.fn<() => Observable<boolean>>() };

  const run: CanActivateFn = (...args) => TestBed.runInInjectionContext(() => adminGuard(...args));
  const activate = async () => {
    const r = run({} as ActivatedRouteSnapshot, {} as RouterStateSnapshot);
    return isObservable(r) ? firstValueFrom(r) : r;
  };
  const url = (r: unknown) => TestBed.inject(Router).serializeUrl(r as UrlTree);

  beforeEach(() => {
    user.set(null);
    auth.checkAuth.mockReset();
    TestBed.configureTestingModule({ providers: [provideRouter([]), { provide: AuthService, useValue: auth }] });
  });

  it('lets an admin in', async () => {
    user.set({ username: 'admin', display_name: 'Sarah Kim', role: 'admin' });
    expect(await activate()).toBe(true);
  });

  it('lets a manager in (they reset analysts\' passwords there)', async () => {
    user.set({ username: 'mira', display_name: 'Mira Cohen', role: 'manager' });
    expect(await activate()).toBe(true);
  });

  it('sends an analyst to the dashboard', async () => {
    user.set({ username: 'alice', display_name: 'Alice Chen', role: 'analyst' });
    expect(url(await activate())).toBe('/dashboard');
  });

  it('loads the session first after a page reload, then decides', async () => {
    auth.checkAuth.mockImplementation(() => {
      user.set({ username: 'admin', display_name: 'Sarah Kim', role: 'admin' });
      return of(true);
    });
    expect(await activate()).toBe(true);
    expect(auth.checkAuth).toHaveBeenCalledOnce();
  });

  it('is not an admin when there is no session', async () => {
    auth.checkAuth.mockReturnValue(of(false));
    expect(await activate()).toBeInstanceOf(UrlTree);
  });
});
