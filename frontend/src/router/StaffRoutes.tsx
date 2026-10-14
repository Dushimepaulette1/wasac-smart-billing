/**
 * @file StaffRoutes.tsx
 * @description The staff portal's pages (built with VITE_APP=staff). Every
 * page but sign-in needs a staff session; Staff accounts needs an admin.
 */

import { Routes, Route, Navigate } from 'react-router-dom';
import StaffSignIn from '../pages/StaffSignIn/StaffSignIn';
import Overview from '../pages/staff/Overview';
import ReviewQueue from '../pages/staff/ReviewQueue';
import Households from '../pages/staff/Households';
import Activity from '../pages/staff/Activity';
import Accounts from '../pages/staff/Accounts';
import MyAccount from '../pages/staff/MyAccount';
import { RequireStaff } from '../staff/auth';

function StaffRoutes() {
  return (
    <Routes>
      <Route path="/staff/sign-in" element={<StaffSignIn />} />
      <Route path="/staff" element={<RequireStaff><Overview /></RequireStaff>} />
      <Route path="/staff/review" element={<RequireStaff><ReviewQueue /></RequireStaff>} />
      <Route path="/staff/households" element={<RequireStaff><Households /></RequireStaff>} />
      <Route path="/staff/activity" element={<RequireStaff><Activity /></RequireStaff>} />
      <Route path="/staff/accounts" element={<RequireStaff role="admin"><Accounts /></RequireStaff>} />
      <Route path="/staff/account" element={<RequireStaff><MyAccount /></RequireStaff>} />
      <Route path="*" element={<Navigate to="/staff" replace />} />
    </Routes>
  );
}

export default StaffRoutes;
