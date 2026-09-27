import { Injectable, inject, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable, of } from 'rxjs';
import { map, catchError, tap, switchMap } from 'rxjs/operators';
import { CurrentUser } from '../auth/permissions';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private http   = inject(HttpClient);
  private router = inject(Router);

  /** The logged-in user, as the server sees it (role = the one it enforces). */
  private readonly _user = signal<CurrentUser | null>(null);
  readonly currentUser     = this._user.asReadonly();
  readonly isAuthenticated = computed(() => this._user() !== null);

  login(username: string, password: string): Observable<CurrentUser> {
    return this.http.post<{ ok: boolean }>('/auth/login', { username, password }).pipe(
      switchMap(() => this.loadCurrentUser()),
    );
  }

  logout() {
    this.http.post('/auth/logout', {}).subscribe();
    this._user.set(null);
    this.router.navigate(['/login']);
  }

  /**
   * Change your own password. The server signs out every other session and
   * re-issues this one's cookie. Disabled in demo mode (server side too).
   */
  changePassword(currentPassword: string, newPassword: string): Observable<CurrentUser> {
    return this.http
      .patch<CurrentUser>('/auth/me', { current_password: currentPassword, new_password: newPassword })
      .pipe(tap(user => this._user.set(user)));
  }

  checkAuth(): Observable<boolean> {
    return this.loadCurrentUser().pipe(
      map(() => true),
      catchError(() => {
        this._user.set(null);
        return of(false);
      }),
    );
  }

  getWsTicket(): Observable<string> {
    return this.http.get<{ ticket: string }>('/auth/ws-ticket').pipe(
      map(r => r.ticket),
    );
  }

  ping(): Observable<void> {
    return this.http.get('/health').pipe(
      map(() => void 0),
      catchError(() => of(void 0)),
    );
  }

  private loadCurrentUser(): Observable<CurrentUser> {
    return this.http.get<CurrentUser>('/auth/me').pipe(
      tap(user => this._user.set(user)),
    );
  }
}
