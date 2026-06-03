import { Injectable, inject, signal, effect } from '@angular/core';
import { DOCUMENT } from '@angular/common';

const THEME_KEY = 'sf_theme';

@Injectable({ providedIn: 'root' })
export class ThemeService {
  private doc = inject(DOCUMENT);

  readonly theme = signal<'dark' | 'light'>(
    (localStorage.getItem(THEME_KEY) as 'dark' | 'light') ?? 'dark'
  );

  constructor() {
    effect(() => {
      this.doc.body.setAttribute('data-theme', this.theme());
      localStorage.setItem(THEME_KEY, this.theme());
    });
  }

  toggle() {
    this.theme.update(t => (t === 'dark' ? 'light' : 'dark'));
  }
}
