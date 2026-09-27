import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { map } from 'rxjs/operators';
import { of } from 'rxjs';
import { AuthService } from '../services/auth';
import { canOpenUserAdmin } from '../auth/permissions';

/**
 * The Users screen: admins and managers (who may only reset analysts'
 * passwords there). UX only: the server checks every action regardless.
 * Everyone else is sent to the dashboard.
 */
export const adminGuard: CanActivateFn = () => {
  const auth   = inject(AuthService);
  const router = inject(Router);
  const decide = () => canOpenUserAdmin(auth.currentUser()).allowed || router.createUrlTree(['/dashboard']);

  return auth.currentUser() ? of(decide()) : auth.checkAuth().pipe(map(decide));
};
