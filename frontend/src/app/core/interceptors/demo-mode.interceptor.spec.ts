import { TestBed } from '@angular/core/testing';
import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { firstValueFrom } from 'rxjs';

import { demoModeInterceptor } from './demo-mode.interceptor';
import { DemoModeService } from '../services/demo-mode.service';

describe('demoModeInterceptor', () => {
  let http: HttpClient;
  let server: HttpTestingController;
  let demo: DemoModeService;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([demoModeInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    http   = TestBed.inject(HttpClient);
    server = TestBed.inject(HttpTestingController);
    demo   = TestBed.inject(DemoModeService);
  });

  // Fails the test if any request reached the "server" that we didn't expect.
  afterEach(() => server.verify());

  describe('in demo mode', () => {
    beforeEach(() => demo.enabled.set(true));

    it('answers a simulated write locally and never sends it', async () => {
      const res = await firstValueFrom(
        http.patch<{ status: string }>('/api/alerts/a1', { status: 'acknowledged' }),
      );

      expect(res.status).toBe('acknowledged');
      server.expectNone('/api/alerts/a1');
      expect(demo.notice()).toContain('simulated');
    });

    it('still sends login and logout to the server', () => {
      http.post('/auth/login', { username: 'u', password: 'p' }).subscribe();
      http.post('/auth/logout', {}).subscribe();

      server.expectOne('/auth/login').flush({ ok: true });
      server.expectOne('/auth/logout').flush({ ok: true });
    });

    it('sends writes it does not simulate, so the server can reject them', () => {
      http.delete('/api/rules/r1').subscribe({ error: () => {} });

      server.expectOne('/api/rules/r1').flush(
        { detail: 'Read-only demo' },
        { status: 403, statusText: 'Forbidden' },
      );
      expect(demo.notice()).toContain('not available');
    });
  });

  describe('outside demo mode', () => {
    beforeEach(() => demo.enabled.set(false));

    it('sends writes to the server unchanged', () => {
      http.patch('/api/alerts/a1', { status: 'acknowledged' }).subscribe();

      const req = server.expectOne('/api/alerts/a1');
      expect(req.request.method).toBe('PATCH');
      req.flush({ id: 'a1', status: 'acknowledged' });
      expect(demo.notice()).toBeNull();
    });
  });

  describe('403 handling', () => {
    it('shows the server reason, not the demo message, for a permission 403', () => {
      let errorStatus = 0;
      http.post('/api/other', {}).subscribe({ error: (e) => (errorStatus = e.status) });

      server.expectOne('/api/other').flush(
        { detail: 'Only the assignee or an admin can change this incident' },
        { status: 403, statusText: 'Forbidden' },
      );

      expect(demo.notice()).toBe('Only the assignee or an admin can change this incident');
      expect(demo.enabled()).toBe(false);  // a permission 403 does not mean demo mode
      expect(errorStatus).toBe(403);       // error still reaches the component
    });

    it('shows nothing for a 403 without a text reason', () => {
      http.post('/api/other', {}).subscribe({ error: () => {} });
      server.expectOne('/api/other').flush({ detail: { html: '<b>x</b>' } }, { status: 403, statusText: 'Forbidden' });
      expect(demo.notice()).toBeNull();
    });
  });
});
