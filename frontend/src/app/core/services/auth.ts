import { Injectable, inject, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable, of } from 'rxjs';
import { map, catchError, tap } from 'rxjs/operators';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private http   = inject(HttpClient);
  private router = inject(Router);

  private readonly _authenticated = signal(false);
  readonly isAuthenticated = computed(() => this._authenticated());

  login(username: string, password: string) {
    return this.http.post<{ ok: boolean }>('/auth/login', { username, password }).pipe(
      tap(() => this._authenticated.set(true)),
    );
  }

  logout() {
    this.http.post('/auth/logout', {}).subscribe();
    this._authenticated.set(false);
    this.router.navigate(['/login']);
  }

  checkAuth(): Observable<boolean> {
    return this.http.get('/auth/me').pipe(
      tap(() => this._authenticated.set(true)),
      map(() => true),
      catchError(() => {
        this._authenticated.set(false);
        return of(false);
      }),
    );
  }

  getWsTicket(): Observable<string> {
    return this.http.get<{ ticket: string }>('/auth/ws-ticket').pipe(
      map(r => r.ticket),
    );
  }
}
