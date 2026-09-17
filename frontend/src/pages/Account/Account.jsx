/**
 * @file Account.jsx
 * @description Customer Profile overview for the currently logged-in WASAC customer.
 */

import React from 'react';
import { useNavigate } from 'react-router-dom';
import PageHeader from '../../components/PageHeader/PageHeader';
import Card from '../../components/Card/Card';
import Button from '../../components/Button/Button';
import StatusBadge from '../../components/StatusBadge/StatusBadge';
import { mockCurrentCustomer } from '../../data/customers';
import styles from './Account.module.css';

export default function Account() {
  const navigate = useNavigate();
  const customer = mockCurrentCustomer;

  return (
    <div className={styles.container}>
      <PageHeader
        title="Customer Profile"
        backHref="/home"
        backLabel="Home"
      />

      <div className={styles.inner}>
        <Card variant="elevated" padding="lg" className={styles.profileCard}>
          <div className={styles.avatarRow}>
            <div className={styles.avatar}>
              {customer.name
                .split(' ')
                .map((n) => n[0])
                .join('')}
            </div>
            <div className={styles.nameMeta}>
              <h2 className={styles.userName}>{customer.name}</h2>
              <span className={styles.userPhone}>+250 {customer.phone}</span>
              <span className={styles.userEmail}>{customer.email}</span>
            </div>
            <div className={styles.statusBadgeWrap}>
              <StatusBadge status={customer.accountStatus} size="sm" />
            </div>
          </div>
        </Card>

        <div className={styles.section}>
          <h3 className={styles.sectionHeading}>Premises & Water Supply</h3>
          <Card variant="default" padding="md" className={styles.detailsCard}>
            <div className={styles.detailRow}>
              <span className={styles.detailKey}>Account Number</span>
              <span className={styles.detailValMono}>{customer.accountNumber}</span>
            </div>
            <div className={styles.detailRow}>
              <span className={styles.detailKey}>Meter Serial</span>
              <span className={styles.detailValMono}>{customer.meterID}</span>
            </div>
            <div className={styles.detailRow}>
              <span className={styles.detailKey}>Physical Address</span>
              <span className={styles.detailVal}>{customer.address}</span>
            </div>
            <div className={styles.detailRow}>
              <span className={styles.detailKey}>Administrative District</span>
              <span className={styles.detailVal}>{customer.district}, Kigali</span>
            </div>
            <div className={styles.detailRow}>
              <span className={styles.detailKey}>Tariff Category</span>
              <span className={styles.detailVal}>Residential Progressive (T1–T4)</span>
            </div>
          </Card>
        </div>

        <div className={styles.section}>
          <h3 className={styles.sectionHeading}>Utility Support</h3>
          <Card variant="default" padding="md" className={styles.detailsCard}>
            <div className={styles.supportRow}>
              <div>
                <div className={styles.supportTitle}>WASAC Emergency Hotline</div>
                <div className={styles.supportSub}>24/7 Leakage and supply alerts</div>
              </div>
              <a href="tel:3535" className={styles.hotlineLink}>
                Call 3535
              </a>
            </div>
            <div className={styles.divider} />
            <div className={styles.supportRow}>
              <div>
                <div className={styles.supportTitle}>Digital Support Center</div>
                <div className={styles.supportSub}>Kigali Central Sector Office</div>
              </div>
              <span className={styles.officeCode}>KG 1 Roundabout</span>
            </div>
          </Card>
        </div>

        <div className={styles.logoutArea}>
          <Button
            variant="ghost"
            size="md"
            fullWidth
            onClick={() => navigate('/')}
          >
            Switch Account or Exit
          </Button>
        </div>
      </div>
    </div>
  );
}
