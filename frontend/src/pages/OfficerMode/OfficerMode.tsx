/**
 * @file OfficerMode.tsx
 * @description Screen 9: Field Officer Operations interface for WASAC.
 */

import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import Card from '../../components/Card/Card';
import Button from '../../components/Button/Button';
import StatusBadge from '../../components/StatusBadge/StatusBadge';
import { mockCustomers, type MockCustomer } from '../../data/customers';
import { mockReadings, mockAnomalyReadings } from '../../data/readings';
import { formatDate, formatConsumption } from '../../utils/format';
import styles from './OfficerMode.module.css';

export default function OfficerMode() {
  const navigate = useNavigate();

  const [sessionCount, setSessionCount] = useState(3);
  const [expandedCustomerId, setExpandedCustomerId] = useState<string | null>(null);
  const [showExitModal, setShowExitModal] = useState(false);

  const toggleExpand = (id: string) => {
    setExpandedCustomerId((curr) => (curr === id ? null : id));
  };

  const handleStartOfficerReading = (customer: MockCustomer) => {
    setSessionCount((prev) => prev + 1);
    navigate('/submit/camera', { state: { officerMode: true, customerId: customer.id } });
  };

  return (
    <div className={styles.container}>
      <header className={styles.officerTopBar}>
        <div className={styles.officerBarInner}>
          <div className={styles.officerBrand}>
            <div className={styles.officerLogoIcon}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path
                  d="M12 2L4 5V11.09C4 16.14 7.41 20.85 12 22C16.59 20.85 20 16.14 20 11.09V5L12 2Z"
                  stroke="var(--color-accent-light)"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>
            <div>
              <span className={styles.officerSystemTitle}>WASAC Mobile Utility</span>
              <div className={styles.officerPill}>Officer Mode · Gasabo District</div>
            </div>
          </div>

          <button
            type="button"
            className={styles.endSessionBtn}
            onClick={() => setShowExitModal(true)}
          >
            End Session
          </button>
        </div>
      </header>

      <div className={styles.inner}>
        <div className={styles.statsBanner}>
          <div className={styles.statBox}>
            <span className={styles.statLabel}>Session Readings</span>
            <span className={styles.statVal}>{sessionCount}</span>
          </div>

          <div className={styles.statDivider} />

          <div className={styles.statBox}>
            <span className={styles.statLabel}>Pending Reviews</span>
            <span className={`${styles.statVal} ${styles.statValWarn}`}>
              {mockAnomalyReadings.length}
            </span>
          </div>

          <div className={styles.statActionBox}>
            <Link to="/officer/review" className={styles.reviewQueueBtn}>
              Open Review Queue
              <svg width="14" height="14" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                <path
                  d="M4 10H16M16 10L11 5M16 10L11 15"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </Link>
          </div>
        </div>

        <section className={styles.customerListSection}>
          <div className={styles.sectionHeader}>
            <h2 className={styles.sectionTitle}>Assigned Route Accounts</h2>
            <span className={styles.accountCount}>
              {mockCustomers.length} properties scheduled
            </span>
          </div>

          <div className={styles.customerStack}>
            {mockCustomers.map((cust) => {
              const isExpanded = expandedCustomerId === cust.id;
              const hasAnomaly = cust.id === 'cust-002';

              return (
                <Card
                  key={cust.id}
                  variant="default"
                  padding="md"
                  className={`${styles.accountCard} ${hasAnomaly ? styles.anomalyBorder : ''}`}
                >
                  <div className={styles.cardMain}>
                    <div className={styles.cardHeaderRow}>
                      <div className={styles.nameBlock}>
                        <h3 className={styles.customerName}>{cust.name}</h3>
                        <span className={styles.addressLine}>{cust.address} · {cust.district}</span>
                      </div>
                      <StatusBadge status={cust.accountStatus} size="sm" />
                    </div>

                    <div className={styles.accountMetaGrid}>
                      <div className={styles.metaCell}>
                        <span className={styles.metaLabel}>Meter ID</span>
                        <span className={styles.metaCode}>{cust.meterID}</span>
                      </div>
                      <div className={styles.metaCell}>
                        <span className={styles.metaLabel}>Previous Verified</span>
                        <span className={styles.metaVal}>{cust.previousReading.toLocaleString()} m³</span>
                      </div>
                      <div className={styles.metaCell}>
                        <span className={styles.metaLabel}>Last Inspection</span>
                        <span className={styles.metaVal}>{formatDate(cust.lastReadingDate)}</span>
                      </div>
                    </div>

                    {hasAnomaly && (
                      <div className={styles.flaggedNotice}>
                        <span className={styles.flagDot} />
                        <span>Recent reading flagged for verification in review queue</span>
                      </div>
                    )}

                    <div className={styles.cardActions}>
                      <Button
                        variant="primary"
                        onClick={() => handleStartOfficerReading(cust)}
                      >
                        Start Reading
                      </Button>
                      <Button
                        variant="secondary"
                        onClick={() => toggleExpand(cust.id)}
                      >
                        {isExpanded ? 'Hide History' : 'View History'}
                      </Button>
                    </div>

                    {isExpanded && (
                      <div className={styles.expandedHistory}>
                        <div className={styles.historyDivider} />
                        <h4 className={styles.historyTitle}>Recent Meter Inspections</h4>
                        <div className={styles.historyTable}>
                          {mockReadings.slice(0, 3).map((r) => (
                            <div key={r.id} className={styles.historyRow}>
                              <span className={styles.historyDate}>{formatDate(r.readingDate)}</span>
                              <span className={styles.historyReading}>{r.reading.toLocaleString()} m³</span>
                              <span className={styles.historyConsump}>+{formatConsumption(r.consumption)}</span>
                              <StatusBadge status={r.status} size="sm" />
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </Card>
              );
            })}
          </div>
        </section>
      </div>

      {showExitModal && (
        <div className={styles.modalBackdrop} onClick={() => setShowExitModal(false)}>
          <div
            className={styles.confirmModal}
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
          >
            <h3 className={styles.modalTitle}>End Officer Session?</h3>
            <p className={styles.modalDesc}>
              You have recorded {sessionCount} readings in this shift. All readings have been synced with WASAC central servers.
            </p>
            <div className={styles.modalButtons}>
              <Button
                variant="primary"
                fullWidth
                onClick={() => navigate('/')}
              >
                End Session and Exit
              </Button>
              <Button
                variant="ghost"
                fullWidth
                onClick={() => setShowExitModal(false)}
              >
                Continue Working
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
