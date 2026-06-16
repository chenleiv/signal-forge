import { HttpInterceptorFn } from '@angular/common/http';
import { environment } from '../../../environments/environment';

export const apiBaseUrlInterceptor: HttpInterceptorFn = (req, next) => {
  if (req.url.startsWith('/')) {
    return next(req.clone({
      url: environment.apiUrl + req.url,
      withCredentials: environment.apiUrl.length > 0,
    }));
  }
  return next(req);
};
