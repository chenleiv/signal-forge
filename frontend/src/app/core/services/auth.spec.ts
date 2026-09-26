import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';

import { AuthService } from './auth';

const ALICE = { username: 'alice', display_name: 'Alice Chen', role: 'analyst' as const };

describe('AuthService', () => {
  let auth: AuthService;
  let server: HttpTestingController;
  const router = { navigate: vi.fn() };

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), { provide: Router, useValue: router }],
    });
    auth = TestBed.inject(AuthService);
    server = TestBed.inject(HttpTestingController);
  });

  afterEach(() => server.verify());

  it('loads the current user from /auth/me after login', async () => {
    const done = firstValueFrom(auth.login('alice', 'pw'));
    server.expectOne('/auth/login').flush({ ok: true });
    server.expectOne('/auth/me').flush(ALICE);

    expect(await done).toEqual(ALICE);
    expect(auth.currentUser()).toEqual(ALICE);
    expect(auth.isAuthenticated()).toBe(true);
  });

  it('stays logged out when login fails', async () => {
    const done = firstValueFrom(auth.login('alice', 'wrong')).catch(e => e.status);
    server.expectOne('/auth/login').flush({ detail: 'Invalid credentials' }, { status: 401, statusText: 'x' });
    server.expectNone('/auth/me');

    expect(await done).toBe(401);
    expect(auth.currentUser()).toBeNull();
  });

  it('checkAuth restores the user from the session cookie, or reports false', async () => {
    const ok = firstValueFrom(auth.checkAuth());
    server.expectOne('/auth/me').flush(ALICE);
    expect(await ok).toBe(true);
    expect(auth.currentUser()).toEqual(ALICE);

    const expired = firstValueFrom(auth.checkAuth());
    server.expectOne('/auth/me').flush({ detail: 'x' }, { status: 401, statusText: 'x' });
    expect(await expired).toBe(false);
    expect(auth.currentUser()).toBeNull();
  });

  it('logout clears the user and goes to /login', () => {
    auth.checkAuth().subscribe();
    server.expectOne('/auth/me').flush(ALICE);

    auth.logout();
    server.expectOne('/auth/logout').flush({ ok: true });

    expect(auth.currentUser()).toBeNull();
    expect(auth.isAuthenticated()).toBe(false);
    expect(router.navigate).toHaveBeenCalledWith(['/login']);
  });
});
