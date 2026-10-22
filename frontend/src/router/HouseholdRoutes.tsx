/**
 * @file HouseholdRoutes.tsx
 * @description The household pages. The start page and sign-in are public;
 * every other page needs the household signed in (RequireHousehold). The
 * staff area is StaffRoutes, under /staff.
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
import SignIn from '../pages/SignIn/SignIn';
import { RequireHousehold } from '../household/session';
import ReadingGate from '../household/ReadingGate';

function HouseholdRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/sign-in" element={<SignIn />} />
      <Route path="/home" element={<RequireHousehold><CustomerHome /></RequireHousehold>} />
      <Route path="/submit/camera" element={<RequireHousehold><ReadingGate><CameraCapture /></ReadingGate></RequireHousehold>} />
      <Route path="/submit/confirm" element={<RequireHousehold><ReadingGate><ConfirmReading /></ReadingGate></RequireHousehold>} />
      <Route path="/submit/held" element={<RequireHousehold><ReadingHeld /></RequireHousehold>} />
      <Route path="/submit/manual" element={<Navigate to="/submit/camera" replace />} />
      <Route path="/bill" element={<RequireHousehold><BillDisplay /></RequireHousehold>} />
      <Route path="/payment" element={<RequireHousehold><Payment /></RequireHousehold>} />
      <Route path="/history" element={<RequireHousehold><BillHistory /></RequireHousehold>} />
      <Route path="/messages" element={<RequireHousehold><Messages /></RequireHousehold>} />

      {import.meta.env.DEV && <Route path="/dev/counter" element={<CounterPreview />} />}

      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}

export default HouseholdRoutes;
