import { HttpInterceptorFn, HttpErrorResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';
import { DemoModeService } from '../services/demo-mode.service';

export const demoModeInterceptor: HttpInterceptorFn = (req, next) => {
  const demo = inject(DemoModeService);

  return next(req).pipe(
    catchError((err: HttpErrorResponse) => {
      if (err.status === 403 && err.error?.detail === 'Read-only demo') {
        demo.showBlocked();
      }
      return throwError(() => err);
    }),
  );
};
