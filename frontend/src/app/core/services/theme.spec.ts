import { TestBed } from '@angular/core/testing';
import { DOCUMENT } from '@angular/common';
import { ThemeService } from './theme';

describe('ThemeService', () => {
  let service: ThemeService;
  let doc: Document;

  beforeEach(() => {
    localStorage.clear();
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({});
    service = TestBed.inject(ThemeService);
    doc = TestBed.inject(DOCUMENT);
  });

  afterEach(() => localStorage.clear());

  it('defaults to dark', () => {
    expect(service.theme()).toBe('dark');
  });

  it('reads saved light theme from localStorage', () => {
    localStorage.setItem('sf_theme', 'light');
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({});
    const fresh = TestBed.inject(ThemeService);
    expect(fresh.theme()).toBe('light');
  });

  it('toggle switches dark → light', () => {
    service.toggle();
    expect(service.theme()).toBe('light');
  });

  it('toggle switches light → dark', () => {
    service.toggle();
    service.toggle();
    expect(service.theme()).toBe('dark');
  });

  it('persists theme to localStorage on toggle', () => {
    service.toggle();
    // Flush pending Angular signal effects
    TestBed.flushEffects();
    expect(localStorage.getItem('sf_theme')).toBe('light');
  });
});
