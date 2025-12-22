import React from 'react';
import styles from '../styles/Layout.module.css';

export default function Layout({ children }) {
  return (
    <div className={styles.layout}>
      <header className={styles.header}>
        <div className={styles.container}>
          <div className={styles.logo}>
            <span style={{ color: '#20BEFF', fontWeight: 900, fontSize: '24px' }}>Kaggle</span>Ingest
          </div>
          {/* Cleared extras */}
        </div>
      </header>
      <main className={styles.main}>
        {children}
      </main>
    </div>
  );
}
