/**
 * @file router/index.tsx
 * @description One site: household pages, and the staff area under /staff.
 * Staff pages are a separate chunk, loaded only when /staff is opened.
 */

import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import HouseholdRoutes from './HouseholdRoutes';

const StaffRoutes = lazy(() => import('./StaffRoutes'));

function AppRouter() {
  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes>
        <Route
          path="/staff/*"
          element={
            <Suspense fallback={null}>
              <StaffRoutes />
            </Suspense>
          }
        />
        <Route path="/officer/*" element={<Navigate to="/staff" replace />} />
        <Route path="*" element={<HouseholdRoutes />} />
      </Routes>
    </BrowserRouter>
  );
}

export default AppRouter;
