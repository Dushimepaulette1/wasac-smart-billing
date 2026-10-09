/**
 * @file router/index.jsx
 * @description Application router configuration for the WASAC Smart Billing Platform.
 * Connects all 11 production screens with responsive shell navigation (SideNav + BottomNav).
 */

import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import BottomNav from '../components/BottomNav/BottomNav';
import SideNav from '../components/SideNav/SideNav';

// Screen Component Imports
import Welcome from '../pages/Welcome/Welcome';
import CustomerHome from '../pages/CustomerHome/CustomerHome';
import CameraCapture from '../pages/CameraCapture/CameraCapture';
import ConfirmReading from '../pages/ConfirmReading/ConfirmReading';
import BillDisplay from '../pages/BillDisplay/BillDisplay';
import Payment from '../pages/Payment/Payment';
import BillHistory from '../pages/BillHistory/BillHistory';
import OfficerMode from '../pages/OfficerMode/OfficerMode';
import AnomalyReview from '../pages/AnomalyReview/AnomalyReview';
import Account from '../pages/Account/Account';
import NotFound from '../pages/NotFound/NotFound';
import CounterPreview from '../pages/_dev/CounterPreview';

/**
 * Shell layout component — wraps screen content with responsive navigation.
 * Conditionally suppresses BottomNav on immersive camera capture and payment screens
 * to prevent touch target overlap on mobile devices.
 */
function AppShell({ children }) {
  const location = useLocation();

  const hideMobileNavPaths = ['/submit/camera', '/payment'];
  const hideBottomNav = hideMobileNavPaths.some((p) => location.pathname.startsWith(p));

  return (
    <div
      style={{
        display: 'flex',
        minHeight: '100vh',
        backgroundColor: 'var(--color-bg-base)',
      }}
    >
      <SideNav />
      <main
        style={{
          flex: 1,
          minHeight: '100vh',
          minWidth: 0,
        }}
      >
        {children}
      </main>
      {!hideBottomNav && <BottomNav />}
    </div>
  );
}

/**
 * AppRouter — root routing component.
 */
function AppRouter() {
  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes>
        <Route path="/" element={<Welcome />} />

        <Route
          path="/home"
          element={
            <AppShell>
              <CustomerHome />
            </AppShell>
          }
        />
        <Route path="/submit/camera" element={<CameraCapture />} />
        <Route path="/submit/confirm" element={<ConfirmReading />} />
        <Route path="/submit/manual" element={<Navigate to="/submit/camera" replace />} />
        <Route
          path="/bill"
          element={
            <AppShell>
              <BillDisplay />
            </AppShell>
          }
        />
        <Route
          path="/payment"
          element={
            <AppShell>
              <Payment />
            </AppShell>
          }
        />
        <Route
          path="/history"
          element={
            <AppShell>
              <BillHistory />
            </AppShell>
          }
        />
        <Route
          path="/account"
          element={
            <AppShell>
              <Account />
            </AppShell>
          }
        />

        <Route
          path="/officer"
          element={
            <AppShell>
              <OfficerMode />
            </AppShell>
          }
        />
        <Route
          path="/officer/review"
          element={
            <AppShell>
              <AnomalyReview />
            </AppShell>
          }
        />

        {process.env.NODE_ENV !== 'production' && (
          <Route path="/dev/counter" element={<CounterPreview />} />
        )}

        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  );
}

export default AppRouter;
