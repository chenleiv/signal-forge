import {
  Component,
  ChangeDetectionStrategy,
  signal,
  inject,
  HostListener,
  viewChild,
  ElementRef,
  effect,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ThreatStoreService } from '../../core/services/threat-store.service';

@Component({
  selector: 'app-command-console',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './command-console.html',
  styleUrl: './command-console.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CommandConsole {
  private store = inject(ThreatStoreService);

  isOpen = signal(false);
  lines = signal<string[]>(['ThreatWatcher Console v1.0 — type "help" for commands']);
  inputValue = signal('');

  private cmdHistory: string[] = [];
  private historyIndex = -1;

  private inputRef = viewChild<ElementRef>('inputRef');
  private outputRef = viewChild<ElementRef>('outputRef');

  constructor() {
    effect(() => {
      if (this.isOpen()) {
        setTimeout(() => this.inputRef()?.nativeElement.focus(), 50);
      }
    });

    effect(() => {
      this.lines();
      setTimeout(() => {
        const el = this.outputRef()?.nativeElement;
        if (el) el.scrollTop = el.scrollHeight;
      }, 0);
    });
  }

  @HostListener('document:keydown', ['$event'])
  onGlobalKey(e: KeyboardEvent) {
    const tag = (document.activeElement as HTMLElement)?.tagName;
    if ((e.key === '`' || e.key === ';') && tag !== 'INPUT' && tag !== 'TEXTAREA') {
      e.preventDefault();
      this.isOpen.update((v) => !v);
    }
    if (e.key === 'Escape') this.isOpen.set(false);
  }

  onInputKey(e: KeyboardEvent) {
    if (e.key === 'Enter') {
      this.submit();
      return;
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (this.historyIndex < this.cmdHistory.length - 1) {
        this.historyIndex++;
        this.inputValue.set(this.cmdHistory[this.cmdHistory.length - 1 - this.historyIndex]);
      }
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      this.historyIndex > 0
        ? this.inputValue.set(this.cmdHistory[this.cmdHistory.length - 1 - --this.historyIndex])
        : ((this.historyIndex = -1), this.inputValue.set(''));
    }
  }

  submit() {
    const cmd = this.inputValue().trim();
    if (!cmd) return;
    this.cmdHistory.push(cmd);
    this.historyIndex = -1;
    this.lines.update((l) => [...l, `> ${cmd}`]);
    this.inputValue.set('');

    if (cmd.toLowerCase() === 'clear') {
      this.lines.set([]);
      return;
    }

    this.store.executeCommand(cmd).subscribe({
      next: (res) => this.lines.update((l) => [...l, res.output]),
      error: () => this.lines.update((l) => [...l, '[ERROR] Command failed']),
    });
  }
}
