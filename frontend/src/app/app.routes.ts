import { Routes } from '@angular/router';
import { AppLayout } from './layout/app-layout/app-layout';
import { authGuard } from './core/guards/auth-guard';

export const routes: Routes = [
  {
    path: 'login',
    loadComponent: () => import('./features/login/login/login').then((m) => m.Login),
  },
  {
    path: '',
    component: AppLayout,
    canActivate: [authGuard],
    children: [
      { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
      {
        path: 'dashboard',
        loadComponent: () => import('./features/dashboard/dashboard').then((m) => m.Dashboard),
      },
      {
        path: 'threats',
        loadComponent: () => import('./features/threats/threats').then((m) => m.Threats),
      },
      {
        path: 'alerts',
        loadComponent: () => import('./features/alerts/alerts').then((m) => m.Alerts),
      },
      {
        path: 'incidents',
        loadComponent: () => import('./features/incidents/incidents').then((m) => m.Incidents),
      },
      {
        path: 'settings',
        loadComponent: () => import('./features/settings/settings').then((m) => m.Settings),
      },
      {
        path: 'map',
        loadComponent: () => import('./features/threat-map/threat-map').then((m) => m.ThreatMap),
      },
      {
        path: 'hunting',
        loadComponent: () => import('./features/threat-hunting/threat-hunting.component').then((m) => m.ThreatHuntingComponent),
      },
      {
        path: 'rules',
        loadComponent: () => import('./features/rules/rules.component').then((m) => m.RulesComponent),
      },
    ],
  },
];
