import { HttpInterceptorFn, HttpErrorResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';

/**
 * An expired or missing session (401) sends the user to /login, except for
 * the /auth/* endpoints themselves (a failed login or session check must not
 * redirect). Matched on the URL's path prefix, not a substring, so a query
 * such as /api/hunt?q=/auth/x still redirects.
 */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const router = inject(Router);

  return next(req).pipe(
    catchError((err: HttpErrorResponse) => {
      const path = new URL(req.url, window.location.origin).pathname;
      if (err.status === 401 && !path.startsWith('/auth/')) {
        router.navigate(['/login']);
      }
      return throwError(() => err);
    }),
  );
};
