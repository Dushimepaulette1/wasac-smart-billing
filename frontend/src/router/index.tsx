/**
 * @file router/index.tsx
 * @description Picks the site this build serves: the household app, or the
 * staff portal when built with VITE_APP=staff. The check is written out on
 * import.meta.env so the build drops the other site's code entirely.
 */

import { lazy, Suspense } from 'react';
import { BrowserRouter } from 'react-router-dom';

const Site =
  import.meta.env.VITE_APP === 'staff'
    ? lazy(() => import('./StaffRoutes'))
    : lazy(() => import('./HouseholdRoutes'));

function AppRouter() {
  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Suspense fallback={null}>
        <Site />
      </Suspense>
    </BrowserRouter>
  );
}

export default AppRouter;
