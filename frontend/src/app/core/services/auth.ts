import { Injectable, inject, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable, of } from 'rxjs';
import { map, catchError, tap } from 'rxjs/operators';

const TOKEN_KEY = 'sf_token';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private http   = inject(HttpClient);
  private router = inject(Router);

  private readonly _authenticated = signal(false);
  readonly isAuthenticated = computed(() => this._authenticated());

  login(username: string, password: string) {
    return this.http.post<{ ok: boolean; token: string }>('/auth/login', { username, password }).pipe(
      tap(res => {
        localStorage.setItem(TOKEN_KEY, res.token);
        this._authenticated.set(true);
      }),
    );
  }

  logout() {
    this.http.post('/auth/logout', {}).subscribe();
    localStorage.removeItem(TOKEN_KEY);
    this._authenticated.set(false);
    this.router.navigate(['/login']);
  }

  checkAuth(): Observable<boolean> {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) return of(false);
    try {
      const b64     = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
      const padded  = b64 + '='.repeat((4 - b64.length % 4) % 4);
      const payload = JSON.parse(atob(padded)) as { exp?: number };
      if (payload.exp && payload.exp * 1000 > Date.now()) {
        this._authenticated.set(true);
        return of(true);
      }
    } catch { /* malformed token */ }
    localStorage.removeItem(TOKEN_KEY);
    return of(false);
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
}
