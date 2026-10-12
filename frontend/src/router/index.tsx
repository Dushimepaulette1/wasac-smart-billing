/**
 * @file router/index.tsx
 * @description Routes. Household pages are public (the household is set by
 * config until household sign-in exists); staff pages need a staff session.
 */

import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Landing from '../pages/Landing/Landing';
import CustomerHome from '../pages/CustomerHome/CustomerHome';
import CameraCapture from '../pages/CameraCapture/CameraCapture';
import ConfirmReading from '../pages/ConfirmReading/ConfirmReading';
import ReadingHeld from '../pages/ReadingHeld/ReadingHeld';
import BillDisplay from '../pages/BillDisplay/BillDisplay';
import Payment from '../pages/Payment/Payment';
import BillHistory from '../pages/BillHistory/BillHistory';
import Messages from '../pages/Messages/Messages';
import NotFound from '../pages/NotFound/NotFound';
import StaffSignIn from '../pages/StaffSignIn/StaffSignIn';
import Overview from '../pages/staff/Overview';
import ReviewQueue from '../pages/staff/ReviewQueue';
import Households from '../pages/staff/Households';
import CounterPreview from '../pages/_dev/CounterPreview';
import { RequireStaff } from '../staff/auth';

function AppRouter() {
  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes>
        <Route path="/" element={<Landing />} />

        {/* Household */}
        <Route path="/home" element={<CustomerHome />} />
        <Route path="/submit/camera" element={<CameraCapture />} />
        <Route path="/submit/confirm" element={<ConfirmReading />} />
        <Route path="/submit/held" element={<ReadingHeld />} />
        <Route path="/submit/manual" element={<Navigate to="/submit/camera" replace />} />
        <Route path="/bill" element={<BillDisplay />} />
        <Route path="/payment" element={<Payment />} />
        <Route path="/history" element={<BillHistory />} />
        <Route path="/messages" element={<Messages />} />

        {/* Staff */}
        <Route path="/staff/sign-in" element={<StaffSignIn />} />
        <Route path="/staff" element={<RequireStaff><Overview /></RequireStaff>} />
        <Route path="/staff/review" element={<RequireStaff><ReviewQueue /></RequireStaff>} />
        <Route path="/staff/households" element={<RequireStaff><Households /></RequireStaff>} />
        <Route path="/officer/*" element={<Navigate to="/staff" replace />} />

        {import.meta.env.DEV && <Route path="/dev/counter" element={<CounterPreview />} />}

        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  );
}

export default AppRouter;
