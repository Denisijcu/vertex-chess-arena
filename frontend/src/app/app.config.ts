import { ApplicationConfig, provideBrowserGlobalErrorListeners, provideZonelessChangeDetection } from '@angular/core';
import { provideRouter, withComponentInputBinding, withNavigationErrorHandler } from '@angular/router';

import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideZonelessChangeDetection(),
    provideRouter(
      routes,
      withComponentInputBinding(),
      // Si se recompila la app con la pestaña abierta, los archivos viejos ya no existen y
      // la navegación falla al cargar la pantalla. En ese caso recargamos la página destino.
      withNavigationErrorHandler((e) => {
        const msg = String((e.error as Error | undefined)?.message ?? e.error ?? '');
        if (/dynamically imported module|Loading chunk|Importing a module script failed/i.test(msg)) {
          window.location.assign(e.url);
        }
      }),
    ),
  ],
};
