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
import { DetectionRule, RuleCondition, RuleAction } from '../../shared/models/threat.models';

const OPERATORS: Record<string, string[]> = {
  score:       ['>', '<', '='],
  attack_type: ['='],
  region:      ['='],
  ip:          ['=', 'contains'],
};

const ATTACK_TYPES = ['SQLi', 'DDoS', 'BruteForce', 'PortScan', 'Malware'];
const REGIONS      = ['US', 'EU', 'RU', 'CN', 'IL', 'BR'];

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

  rules    = signal<DetectionRule[]>([]);
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
      .subscribe(r => this.rules.set(r));
  }

  newRule() {
    this.selected.set(null);
    this.isNew.set(true);
    this.editName.set('');
    this.editLogic.set('AND');
    this.editConditions.set([{ field: 'score', operator: '>', value: 75 }]);
    this.editActions.set(new Set<RuleAction>(['alert']));
  }

  selectRule(rule: DetectionRule) {
    this.selected.set(rule);
    this.isNew.set(false);
    this.editName.set(rule.name);
    this.editLogic.set(rule.logic);
    this.editConditions.set(rule.conditions.map(c => ({ ...c })));
    this.editActions.set(new Set<RuleAction>(rule.actions));
  }

  addCondition() {
    this.editConditions.update(cs => [...cs, { field: 'score', operator: '>', value: 0 }]);
  }

  removeCondition(i: number) {
    this.editConditions.update(cs => cs.filter((_, idx) => idx !== i));
  }

  updateConditionField(i: number, field: string) {
    const ops = OPERATORS[field] ?? ['='];
    this.editConditions.update(cs =>
      cs.map((c, idx) => idx === i
        ? { ...c, field: field as RuleCondition['field'], operator: ops[0] as RuleCondition['operator'], value: '' }
        : c)
    );
  }

  updateConditionOp(i: number, operator: string) {
    this.editConditions.update(cs =>
      cs.map((c, idx) => idx === i ? { ...c, operator: operator as RuleCondition['operator'] } : c)
    );
  }

  updateConditionValue(i: number, value: string) {
    this.editConditions.update(cs =>
      cs.map((c, idx) => idx === i ? { ...c, value } : c)
    );
  }

  toggleAction(action: RuleAction) {
    this.editActions.update(set => {
      const next = new Set(set);
      next.has(action) ? next.delete(action) : next.add(action);
      return next;
    });
  }

  save() {
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
          this.selected.set(updated);
        });
    } else {
      this.store.createRule(payload)
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe(created => {
          this.rules.update(list => [...list, created]);
          this.selected.set(created);
          this.isNew.set(false);
        });
    }
  }

  toggleEnabled(rule: DetectionRule, e: Event) {
    e.stopPropagation();
    this.store.updateRule(rule.id, { enabled: !rule.enabled })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(updated => {
        this.rules.update(list => list.map(r => r.id === updated.id ? updated : r));
        if (this.selected()?.id === updated.id) this.selected.set(updated);
      });
  }

  deleteRule(rule: DetectionRule, e: Event) {
    e.stopPropagation();
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

  cancel() {
    const rule = this.selected();
    if (rule) this.selectRule(rule);
    else { this.selected.set(null); this.isNew.set(false); }
  }

  valueOptions(field: string): string[] {
    if (field === 'attack_type') return ATTACK_TYPES;
    if (field === 'region')      return REGIONS;
    return [];
  }
}
