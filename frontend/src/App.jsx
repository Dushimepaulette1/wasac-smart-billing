import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import CameraScreen from './pages/CameraScreen';
import ConfirmReading from './pages/ConfirmReading';
import BillDisplay from './pages/BillDisplay';
import PaymentScreen from './pages/PaymentScreen';
import OfficerMode from './pages/OfficerMode';
import './App.css';

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-shell">
        <header className="app-header">
          <div className="header-inner">
            <span className="header-logo">💧</span>
            <span className="header-title">WASAC Smart Billing</span>
          </div>
        </header>
        <main className="app-main">
          <Routes>
            <Route path="/" element={<Navigate to="/camera" replace />} />
            <Route path="/camera" element={<CameraScreen />} />
            <Route path="/confirm" element={<ConfirmReading />} />
            <Route path="/bill" element={<BillDisplay />} />
            <Route path="/payment" element={<PaymentScreen />} />
            <Route path="/officer" element={<OfficerMode />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
