/**
 * @file HouseholdRoutes.tsx
 * @description The household pages. The staff area is StaffRoutes, under /staff.
 */

import { Routes, Route, Navigate } from 'react-router-dom';
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
import CounterPreview from '../pages/_dev/CounterPreview';

function HouseholdRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/home" element={<CustomerHome />} />
      <Route path="/submit/camera" element={<CameraCapture />} />
      <Route path="/submit/confirm" element={<ConfirmReading />} />
      <Route path="/submit/held" element={<ReadingHeld />} />
      <Route path="/submit/manual" element={<Navigate to="/submit/camera" replace />} />
      <Route path="/bill" element={<BillDisplay />} />
      <Route path="/payment" element={<Payment />} />
      <Route path="/history" element={<BillHistory />} />
      <Route path="/messages" element={<Messages />} />

      {import.meta.env.DEV && <Route path="/dev/counter" element={<CounterPreview />} />}

      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}

export default HouseholdRoutes;
