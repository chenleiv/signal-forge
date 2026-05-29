import { Routes } from '@angular/router';
import { AppLayout } from './layout/app-layout/app-layout';
import { Dashboard } from './features/dashboard/dashboard';
import { Threats } from './features/threats/threats';
import { Alerts } from './features/alerts/alerts';
import { Incidents } from './features/incidents/incidents';
import { Settings } from './features/settings/settings';

export const routes: Routes = [
  {
    path: '',

    component: AppLayout,

    children: [
      { path: '', redirectTo: 'dashboard', pathMatch: 'full' },

      { path: 'dashboard', component: Dashboard },

      { path: 'threats', component: Threats },

      { path: 'alerts', component: Alerts },

      { path: 'incidents', component: Incidents },

      { path: 'settings', component: Settings },

      {
        path: 'map',
        loadComponent: () => import('./features/threat-map/threat-map').then((m) => m.ThreatMap),
      },
    ],
  },
];
