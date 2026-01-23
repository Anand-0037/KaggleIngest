import React, { useState, useEffect } from 'react';
import styles from './LoadingState.module.css';

export default function LoadingState() {
  const [stage, setStage] = useState(0);
  const messages = [
    "Connecting to Kaggle...",
    "Fetching Competition Metadata...",
    "Analyzing Top Notebooks...",
    "Compressing to TOON Format...",
    "Finalizing Context..."
  ];

  useEffect(() => {
    const interval = setInterval(() => {
      setStage(s => (s < messages.length - 1 ? s + 1 : s));
    }, 2500);
    return () => clearInterval(interval);
  }, [messages.length]);

  return (
    <div className={styles.loadingCard}>
      <div className={styles.header}>
        <div className={styles.spinner}></div>
        <span className={styles.title}>{messages[stage]}</span>
      </div>

      <div className={styles.skeletonBlock}>
        <div className={`${styles.skeletonLine} ${styles.medium}`}></div>
        <div className={`${styles.skeletonLine} ${styles.short}`}></div>
        <div className={`${styles.skeletonLine} ${styles.long}`}></div>
        <div className={`${styles.skeletonLine} ${styles.medium}`}></div>
        <div className={`${styles.skeletonLine} ${styles.short}`}></div>
      </div>
    </div>
  );
}
