import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { apiBaseUrlInterceptor } from './core/interceptors/api-base-url.interceptor';
import { provideEchartsCore } from 'ngx-echarts';
import { authInterceptor } from './core/interceptors/auth.interceptor';

import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes),
    provideHttpClient(withInterceptors([apiBaseUrlInterceptor, authInterceptor])),
    provideEchartsCore({ echarts: () => import('echarts') }),
  ],
};
