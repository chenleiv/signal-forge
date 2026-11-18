import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { of } from 'rxjs';
import { Settings } from './settings';
import { AuthService } from '../../core/services/auth';
import { DemoModeService } from '../../core/services/demo-mode.service';
import { SettingsService } from '../../core/services/settings.service';

const ALICE = { username: 'alice', display_name: 'Alice Chen', role: 'analyst' as const };

describe('Settings: Save is enabled only when something changed', () => {
  function create() {
    TestBed.configureTestingModule({
      imports: [Settings],
      providers: [
        { provide: AuthService, useValue: { currentUser: signal(ALICE), changePassword: vi.fn(() => of(ALICE)), logout: vi.fn() } },
        { provide: DemoModeService, useValue: { enabled: signal(false) } },
      ],
    });
    const fixture = TestBed.createComponent(Settings);
    fixture.detectChanges();
    return fixture;
  }

  const el = (f: ReturnType<typeof create>) => f.nativeElement as HTMLElement;
  const saveBtn = (f: ReturnType<typeof create>) => el(f).querySelector('.actions .btn-save') as HTMLButtonElement;
  const type = (f: ReturnType<typeof create>, id: string, value: string) => {
    const input = el(f).querySelector(`#${id}`) as HTMLInputElement;
    input.value = value;
    input.dispatchEvent(new Event('input'));
    f.detectChanges();
  };

  beforeEach(() => localStorage.clear());
  afterEach(() => { vi.useRealTimers(); localStorage.clear(); });

  it('is disabled on load, and save() called directly stores nothing', () => {
    const f = create();
    const store = vi.spyOn(TestBed.inject(SettingsService), 'save');
    expect(f.componentInstance.dirty()).toBe(false);
    expect(saveBtn(f).disabled).toBe(true);

    f.componentInstance.save();
    expect(store).not.toHaveBeenCalled();
    expect(f.componentInstance.saved()).toBe(false);
  });

  it('a change enables it, and reverting the value disables it again', () => {
    const f = create();
    const original = (el(f).querySelector('#buffer-size') as HTMLInputElement).value;

    type(f, 'buffer-size', '250');
    expect(saveBtn(f).disabled).toBe(false);

    type(f, 'buffer-size', original);
    expect(saveBtn(f).disabled).toBe(true);
  });

  it('a successful save stores the form, shows Saved for 2 seconds and stays disabled', () => {
    vi.useFakeTimers();
    const f = create();
    const svc = TestBed.inject(SettingsService);

    type(f, 'buffer-size', '250');
    saveBtn(f).click();
    f.detectChanges();

    expect(svc.settings().bufferSize).toBe(250);
    expect(saveBtn(f).disabled).toBe(true);
    expect(saveBtn(f).textContent).toContain('Saved');

    vi.advanceTimersByTime(2000);
    f.detectChanges();
    expect(saveBtn(f).textContent).toContain('Save Settings');
    expect(saveBtn(f).disabled).toBe(true);
  });

  it('a new change after a save enables it again', () => {
    const f = create();
    type(f, 'reconnect-delay', '7');
    f.componentInstance.save();
    f.detectChanges();
    expect(saveBtn(f).disabled).toBe(true);

    type(f, 'reconnect-delay', '8');
    expect(saveBtn(f).disabled).toBe(false);
  });

  it('Reset to Defaults leaves nothing to save', () => {
    const f = create();
    type(f, 'ws-url', 'wss://soc.example/ws/threats');
    f.componentInstance.save();
    f.componentInstance.reset();
    f.detectChanges();
    expect(saveBtn(f).disabled).toBe(true);
  });

  it('the password button keeps its own rule: disabled until the form is valid', () => {
    const f = create();
    const pwBtn = el(f).querySelector('.pw-details .btn-save') as HTMLButtonElement;
    expect(pwBtn.disabled).toBe(true);

    const c = f.componentInstance;
    c.currentPw.set('my-current-password');
    c.newPw.set('a-brand-new-password-9');
    c.confirmPw.set('a-brand-new-password-9');
    f.detectChanges();
    expect(pwBtn.disabled).toBe(false);
  });
});
