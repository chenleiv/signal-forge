import { HttpErrorResponse, HttpInterceptorFn, HttpResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, delay, map, of, throwError } from 'rxjs';
import { DemoModeService } from '../services/demo-mode.service';
import { DemoSimulatorService } from '../services/demo-simulator.service';

const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS']);
const PASS_THROUGH_WRITES = new Set(['/auth/login', '/auth/logout']);
const SIMULATED_LATENCY_MS = 150;

/**
 * Demo mode, client side: writes are checked against the permission matrix,
 * then simulated locally (never sent); GETs get the local overlay; a server
 * 403 shows as a notice. UX only: the server enforces read-only mode anyway.
 */
export const demoModeInterceptor: HttpInterceptorFn = (req, next) => {
  const demo = inject(DemoModeService);
  const sim  = inject(DemoSimulatorService);
  const path = new URL(req.url, window.location.origin).pathname;

  if (demo.enabled() && !SAFE_METHODS.has(req.method) && !PASS_THROUGH_WRITES.has(path)) {
    // Same permission matrix as the server: a denied action fails like the
    // real API would (403 + reason), simulated or not.
    const decision = sim.authorize(req, path);
    if (!decision.allowed) {
      demo.showDenied(decision.reason);
      return throwError(() => new HttpErrorResponse({
        status: 403, statusText: 'Forbidden', url: req.url, error: { detail: decision.reason },
      }));
    }
    const result = sim.simulate(req, path);
    if (result) {
      demo.showSimulated();
      return of(new HttpResponse({ status: 200, body: result.body, url: req.url }))
        .pipe(delay(SIMULATED_LATENCY_MS));
    }
  }

  return next(req).pipe(
    map(event =>
      demo.enabled() && req.method === 'GET' && event instanceof HttpResponse
        ? event.clone({ body: sim.overlay(path, event.body) })
        : event,
    ),
    catchError((err: HttpErrorResponse) => {
      const detail: unknown = err.error?.detail;
      if (err.status === 403 && detail === 'Read-only demo') {
        demo.showBlocked();
      } else if (err.status === 403 && typeof detail === 'string') {
        demo.showDenied(detail);  // e.g. "Only the assignee or an admin can …"
      }
      return throwError(() => err);
    }),
  );
};
