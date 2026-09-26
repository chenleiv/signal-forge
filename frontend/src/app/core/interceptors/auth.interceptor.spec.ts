import { TestBed } from '@angular/core/testing';
import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Router } from '@angular/router';
import { authInterceptor } from './auth.interceptor';

describe('authInterceptor', () => {
  let http: HttpClient;
  let server: HttpTestingController;
  const router = { navigate: vi.fn() };

  beforeEach(() => {
    router.navigate.mockClear();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
        { provide: Router, useValue: router },
      ],
    });
    http = TestBed.inject(HttpClient);
    server = TestBed.inject(HttpTestingController);
  });

  afterEach(() => server.verify());

  function respond(url: string, status: number) {
    let error: number | null = null;
    http.get(url).subscribe({ error: e => (error = e.status) });
    server.expectOne(url).flush({ detail: 'x' }, { status, statusText: 'x' });
    return error;
  }

  it.each([
    '/api/incidents',
    'http://localhost:8000/api/rules',              // absolute URL (dev API base)
    '/api/hunt?q=/auth/x',                           // "/auth/" only in the query
    '/api/users/auth/',                              // "/auth/" later in the path
  ])('401 on %s redirects to /login', url => {
    expect(respond(url, 401)).toBe(401);  // the error still reaches the caller
    expect(router.navigate).toHaveBeenCalledWith(['/login']);
  });

  it.each(['/auth/me', '/auth/login', 'http://localhost:8000/auth/ws-ticket'])(
    '401 on %s does not redirect',
    url => {
      respond(url, 401);
      expect(router.navigate).not.toHaveBeenCalled();
    },
  );

  it.each([403, 404, 500])('%s does not redirect', status => {
    respond('/api/incidents', status);
    expect(router.navigate).not.toHaveBeenCalled();
  });
});
