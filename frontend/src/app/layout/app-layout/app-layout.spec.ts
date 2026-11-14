import { Component, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { AppLayout } from './app-layout';
import { CommandConsole } from '../../features/command-console/command-console';
import { ThreatsService, StreamStatus } from '../../core/services/threats.service';
import { ThreatStoreService } from '../../core/services/threat-store.service';
import { AuthService } from '../../core/services/auth';
import { ThemeService } from '../../core/services/theme';
import { DemoModeService } from '../../core/services/demo-mode.service';
import { ThreatFeedService } from '../../core/services/threat-feed.service';

@Component({ selector: 'app-command-console', template: '' })
class ConsoleStub {
  isOpen = signal(false);
}

describe('AppLayout: live-feed chip', () => {
  const status = signal<StreamStatus>('disconnected');

  function create() {
    TestBed.configureTestingModule({
      imports: [AppLayout],
      providers: [
        provideRouter([]),
        {
          provide: ThreatsService,
          useValue: { status, slowConnection: signal(false), connect: vi.fn(), disconnect: vi.fn() },
        },
        { provide: ThreatStoreService, useValue: { newAlertCount: signal(0) } },
        {
          provide: AuthService,
          useValue: {
            currentUser: signal({ username: 'alice', display_name: 'Alice Chen', role: 'analyst' }),
            logout: vi.fn(),
          },
        },
        { provide: ThemeService, useValue: { theme: signal('dark') } },
        {
          provide: DemoModeService,
          useValue: { enabled: signal(false), notice: signal(null), load: vi.fn(), dismiss: vi.fn() },
        },
        { provide: ThreatFeedService, useValue: { notice: signal(null), watch: vi.fn() } },
      ],
    });
    TestBed.overrideComponent(AppLayout, {
      remove: { imports: [CommandConsole] },
      add: { imports: [ConsoleStub] },
    });
    const fixture = TestBed.createComponent(AppLayout);
    fixture.detectChanges();
    return fixture;
  }

  function chipFor(next: StreamStatus) {
    status.set(next);
    const fixture = create();
    const chip = fixture.nativeElement.querySelector('.topbar-chip') as HTMLElement;
    const dot = chip.querySelector('.chip-dot') as HTMLElement;
    return { chip, dot };
  }

  beforeEach(() => status.set('disconnected'));

  it('connected: green live chip', () => {
    const { chip, dot } = chipFor('connected');
    expect(chip.classList).toContain('chip-live');
    expect(chip.classList).not.toContain('chip-reconnecting');
    expect(chip.classList).not.toContain('chip-signed-out');
    expect(dot.classList).not.toContain('dot-reconnecting');
    expect(chip.textContent).toContain('LIVE FEED');
  });

  it('reconnecting: warning chip', () => {
    const { chip, dot } = chipFor('reconnecting');
    expect(chip.classList).toContain('chip-reconnecting');
    expect(chip.classList).not.toContain('chip-live');
    expect(dot.classList).toContain('dot-reconnecting');
    expect(chip.textContent).toContain('RECONNECTING');
  });

  it('disconnected: warning chip, never green', () => {
    const { chip, dot } = chipFor('disconnected');
    expect(chip.classList).toContain('chip-reconnecting');
    expect(chip.classList).not.toContain('chip-live');
    expect(dot.classList).toContain('dot-reconnecting');
    expect(chip.textContent).toContain('RECONNECTING');
  });

  it('signed out: neutral chip', () => {
    const { chip, dot } = chipFor('signed-out');
    expect(chip.classList).toContain('chip-signed-out');
    expect(chip.classList).not.toContain('chip-live');
    expect(chip.classList).not.toContain('chip-reconnecting');
    expect(dot.classList).toContain('dot-signed-out');
    expect(chip.textContent).toContain('SIGNED OUT');
  });
});
