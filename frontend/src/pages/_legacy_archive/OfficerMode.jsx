import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import styles from './OfficerMode.module.css';

const API = 'http://localhost:8000';

export default function OfficerMode() {
  const navigate = useNavigate();
  const [loggedIn, setLoggedIn] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(false);

  const handleLogin = (e) => {
    e.preventDefault();
    if (username === 'officer' && password === 'wasac2024') {
      setLoggedIn(true);
      setLoginError('');
    } else {
      setLoginError('Invalid credentials. Use officer / wasac2024');
    }
  };

  useEffect(() => {
    if (!loggedIn) return;
    setLoading(true);
    fetch(`${API}/customers`)
      .then(r => r.json())
      .then(data => { setCustomers(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [loggedIn]);

  if (!loggedIn) {
    return (
      <div className={styles.container}>
        <div className={styles.loginCard}>
          <div className={styles.loginIcon}>👮</div>
          <h2 className={styles.loginTitle}>Officer Mode</h2>
          <p className={styles.loginSub}>WASAC Field Agent Access</p>

          <form onSubmit={handleLogin} className={styles.form}>
            <div className={styles.field}>
              <label>Username</label>
              <input
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                placeholder="officer"
                autoComplete="username"
              />
            </div>
            <div className={styles.field}>
              <label>Password</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                autoComplete="current-password"
              />
            </div>
            {loginError && <p className={styles.error}>{loginError}</p>}
            <button type="submit" className="btn btn-primary">
              Sign In
            </button>
          </form>
          <button className="btn btn-ghost" style={{ marginTop: 10 }} onClick={() => navigate('/camera')}>
            ← Back to Customer View
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <div className={styles.dashHeader}>
        <h2>Field Dashboard</h2>
        <button className={styles.logoutBtn} onClick={() => setLoggedIn(false)}>Log out</button>
      </div>

      {loading ? (
        <div className="spinner-wrap"><div className="spinner" /><span>Loading accounts…</span></div>
      ) : (
        <div className={styles.accountList}>
          {customers.map(c => (
            <div key={c.customer_id} className={styles.accountCard}>
              <div className={styles.accountTop}>
                <div>
                  <div className={styles.accountName}>{c.name}</div>
                  <div className={styles.accountMeta}>{c.sector} · {c.meter_id}</div>
                </div>
                {c.anomaly_flagged && (
                  <span className="badge badge-yellow">⚠ Anomaly</span>
                )}
              </div>

              <div className={styles.stats}>
                <div className={styles.stat}>
                  <span className={styles.statLabel}>Last Reading</span>
                  <span className={styles.statValue}>{c.last_reading?.toFixed(1)} m³</span>
                </div>
                <div className={styles.stat}>
                  <span className={styles.statLabel}>Avg/Month</span>
                  <span className={styles.statValue}>{c.avg_consumption ?? '—'} m³</span>
                </div>
                <div className={styles.stat}>
                  <span className={styles.statLabel}>Phone</span>
                  <span className={styles.statValue}>{c.phone}</span>
                </div>
              </div>

              <button
                className="btn btn-primary"
                style={{ marginTop: 12 }}
                onClick={() =>
                  navigate('/camera', {
                    state: { officerMode: true, customerId: c.customer_id, meterId: c.meter_id },
                  })
                }
              >
                📷 Submit Reading
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
