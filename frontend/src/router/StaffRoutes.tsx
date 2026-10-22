/**
 * @file StaffRoutes.tsx
 * @description The staff area, under /staff (paths here are relative to it).
 * Every page but sign-in needs a staff session; Staff accounts needs an admin.
 * Loaded only when someone opens /staff, so households never download it.
 */

import { Routes, Route, Navigate } from 'react-router-dom';
import StaffSignIn from '../pages/StaffSignIn/StaffSignIn';
import Overview from '../pages/staff/Overview';
import ReviewQueue from '../pages/staff/ReviewQueue';
import Households from '../pages/staff/Households';
import Activity from '../pages/staff/Activity';
import Accounts from '../pages/staff/Accounts';
import MyAccount from '../pages/staff/MyAccount';
import SmsOutbox from '../pages/staff/SmsOutbox';
import { RequireStaff } from '../staff/auth';

function StaffRoutes() {
  return (
    <Routes>
      <Route path="sign-in" element={<StaffSignIn />} />
      <Route index element={<RequireStaff><Overview /></RequireStaff>} />
      <Route path="review" element={<RequireStaff><ReviewQueue /></RequireStaff>} />
      <Route path="households" element={<RequireStaff><Households /></RequireStaff>} />
      <Route path="activity" element={<RequireStaff><Activity /></RequireStaff>} />
      <Route path="accounts" element={<RequireStaff role="admin"><Accounts /></RequireStaff>} />
      <Route path="account" element={<RequireStaff><MyAccount /></RequireStaff>} />
      <Route path="sms" element={<RequireStaff role="admin"><SmsOutbox /></RequireStaff>} />
      <Route path="*" element={<Navigate to="/staff" replace />} />
    </Routes>
  );
}

export default StaffRoutes;
