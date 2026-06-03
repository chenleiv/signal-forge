import { Injectable, inject, signal, effect } from '@angular/core';
import { DOCUMENT } from '@angular/common';

const THEME_KEY = 'sf_theme';

@Injectable({ providedIn: 'root' })
export class ThemeService {
  private doc = inject(DOCUMENT);
  private storage = this.doc.defaultView?.localStorage;

  readonly theme = signal<'dark' | 'light'>(
    this.storage?.getItem(THEME_KEY) === 'light' ? 'light' : 'dark'
  );

  constructor() {
    effect(() => {
      this.doc.documentElement.setAttribute('data-theme', this.theme());
      this.storage?.setItem(THEME_KEY, this.theme());
    });
  }

  toggle() {
    this.theme.update(t => (t === 'dark' ? 'light' : 'dark'));
  }
}
