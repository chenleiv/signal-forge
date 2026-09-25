import { HttpErrorResponse, HttpInterceptorFn, HttpResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, delay, map, of, throwError } from 'rxjs';
import { DemoModeService } from '../services/demo-mode.service';
import { DemoSimulatorService } from '../services/demo-simulator.service';

const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS']);
const PASS_THROUGH_WRITES = new Set(['/auth/login', '/auth/logout']);
const SIMULATED_LATENCY_MS = 150;

/**
 * Demo mode, client side:
 *  - writes are answered locally by DemoSimulatorService and never sent;
 *  - GET responses get the local overlay applied, so the UI stays consistent;
 *  - a server 403 "Read-only demo" (anything not simulated) becomes a notice.
 * UX only: the server enforces read-only mode whether or not this runs.
 */
export const demoModeInterceptor: HttpInterceptorFn = (req, next) => {
  const demo = inject(DemoModeService);
  const sim  = inject(DemoSimulatorService);
  const path = new URL(req.url, window.location.origin).pathname;

  if (demo.enabled() && !SAFE_METHODS.has(req.method) && !PASS_THROUGH_WRITES.has(path)) {
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
      if (err.status === 403 && err.error?.detail === 'Read-only demo') {
        demo.showBlocked();
      }
      return throwError(() => err);
    }),
  );
};
