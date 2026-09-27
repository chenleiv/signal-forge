import {
  Component,
  inject,
  signal,
  computed,
  ChangeDetectionStrategy,
  DestroyRef,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ThreatStoreService } from '../../core/services/threat-store.service';
import { AuthService } from '../../core/services/auth';
import { canManageConfiguration } from '../../core/auth/permissions';
import { DetectionRule, RuleCondition, RuleAction, ATTACK_TYPES, REGIONS } from '../../shared/models/threat.models';

const OPERATORS: Record<string, string[]> = {
  score:       ['>', '<', '='],
  attack_type: ['='],
  region:      ['='],
  ip:          ['=', 'contains'],
};

@Component({
  selector: 'app-rules',
  standalone: true,
  imports: [],
  templateUrl: './rules.component.html',
  styleUrl: './rules.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RulesComponent {
  private store      = inject(ThreatStoreService);
  private destroyRef = inject(DestroyRef);
  private auth       = inject(AuthService);

  /** Rules are admin-only to change (UX only; the server enforces it). */
  readonly manage       = computed(() => canManageConfiguration(this.auth.currentUser()));
  readonly manageReason = computed(() => { const d = this.manage(); return d.allowed ? null : d.reason; });

  rules    = signal<DetectionRule[]>([]);
  loading  = signal(true);
  selected = signal<DetectionRule | null>(null);
  isNew    = signal(false);

  editName       = signal('');
  editLogic      = signal<'AND' | 'OR'>('AND');
  editConditions = signal<RuleCondition[]>([{ field: 'score', operator: '>', value: 75 }]);
  editActions    = signal<Set<RuleAction>>(new Set<RuleAction>(['alert']));

  readonly operatorsFor = (field: string) => OPERATORS[field] ?? ['='];
  readonly attackTypes  = ATTACK_TYPES;
  readonly regions      = REGIONS;
  readonly allActions: RuleAction[] = ['alert', 'incident', 'block'];

  readonly queryPreview = computed(() => {
    const parts = this.editConditions().map(c => `${c.field}${c.operator}${c.value}`);
    return parts.length ? parts.join(` ${this.editLogic()} `) : '—';
  });

  constructor() {
    this.store.getRules()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(r => { this.rules.set(r); this.loading.set(false); });
  }

  private loadEditor(rule?: DetectionRule) {
    this.editName.set(rule?.name ?? '');
    this.editLogic.set(rule?.logic ?? 'AND');
    this.editConditions.set(rule ? rule.conditions.map(c => ({ ...c })) : [{ field: 'score', operator: '>', value: 75 }]);
    this.editActions.set(new Set<RuleAction>(rule?.actions ?? ['alert']));
  }

  // Every write handler re-checks the permission: aria-disabled controls stay clickable.
  newRule() {
    if (!this.manage().allowed) return;
    this.selected.set(null);
    this.isNew.set(true);
    this.loadEditor();
  }

  selectRule(rule: DetectionRule) {
    this.selected.set(rule);
    this.isNew.set(false);
    this.loadEditor(rule);
  }

  addCondition() {
    this.editConditions.update(cs => [...cs, { field: 'score', operator: '>', value: 0 }]);
  }

  removeCondition(i: number) {
    this.editConditions.update(cs => cs.filter((_, idx) => idx !== i));
  }

  private updateCondition(i: number, patch: Partial<RuleCondition>) {
    this.editConditions.update(cs => cs.map((c, idx) => idx === i ? { ...c, ...patch } : c));
  }

  updateConditionField(i: number, field: string) {
    const ops = OPERATORS[field] ?? ['='];
    this.updateCondition(i, { field: field as RuleCondition['field'], operator: ops[0] as RuleCondition['operator'], value: '' });
  }

  updateConditionOp(i: number, operator: string) {
    this.updateCondition(i, { operator: operator as RuleCondition['operator'] });
  }

  updateConditionValue(i: number, value: string) {
    this.updateCondition(i, { value });
  }

  toggleAction(action: RuleAction) {
    this.editActions.update(set => {
      const next = new Set(set);
      next.has(action) ? next.delete(action) : next.add(action);
      return next;
    });
  }

  save() {
    if (!this.manage().allowed) return;
    const payload = {
      name:       this.editName().trim() || 'Unnamed Rule',
      logic:      this.editLogic(),
      conditions: this.editConditions(),
      actions:    [...this.editActions()] as RuleAction[],
      enabled:    true,
    };
    const rule = this.selected();
    if (rule) {
      this.store.updateRule(rule.id, payload)
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe(updated => {
          this.rules.update(list => list.map(r => r.id === updated.id ? updated : r));
          this.selected.set(null);
          this.isNew.set(false);
        });
    } else {
      this.store.createRule(payload)
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe(created => {
          this.rules.update(list => [...list, created]);
          this.selected.set(null);
          this.isNew.set(false);
        });
    }
  }

  toggleEnabled(rule: DetectionRule, e: Event) {
    e.stopPropagation();
    if (!this.manage().allowed) return;
    this.store.updateRule(rule.id, { enabled: !rule.enabled })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(updated => {
        this.rules.update(list => list.map(r => r.id === updated.id ? updated : r));
        if (this.selected()?.id === updated.id) this.selected.set(updated);
      });
  }

  deleteRule(rule: DetectionRule, e: Event) {
    e.stopPropagation();
    if (!this.manage().allowed) return;
    this.store.deleteRule(rule.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(() => {
        this.rules.update(list => list.filter(r => r.id !== rule.id));
        if (this.selected()?.id === rule.id) {
          this.selected.set(null);
          this.isNew.set(false);
        }
      });
  }

  /** Leave the editor (narrow screens: back to the rule list). Not a write. */
  closeEditor() {
    this.selected.set(null);
    this.isNew.set(false);
  }

  cancel() {
    const rule = this.selected();
    if (rule) this.selectRule(rule);
    else { this.selected.set(null); this.isNew.set(false); }
  }

  valueOptions(field: string): readonly string[] {
    if (field === 'attack_type') return ATTACK_TYPES;
    if (field === 'region')      return REGIONS;
    return [];
  }
}
