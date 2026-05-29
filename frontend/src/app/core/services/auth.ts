import { Injectable, inject, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { tap } from 'rxjs/operators';

const TOKEN_KEY = 'sf_token';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private http = inject(HttpClient);
  private router = inject(Router);

  private token = signal<string | null>(localStorage.getItem(TOKEN_KEY));

  readonly isAuthenticated = computed(() => !!this.token());

  login(username: string, password: string) {
    return this.http.post<{ access_token: string }>('/auth/login', { username, password }).pipe(
      tap((res) => {
        this.token.set(res.access_token);
        localStorage.setItem(TOKEN_KEY, res.access_token);
      }),
    );
  }

  logout() {
    this.token.set(null);
    localStorage.removeItem(TOKEN_KEY);
    this.router.navigate(['/login']);
  }
}
