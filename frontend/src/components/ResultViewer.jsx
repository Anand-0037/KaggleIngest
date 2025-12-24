import React, { useState, useEffect } from 'react';
import { getJobDownloadUrl } from '../services/api';
import { useTheme } from '../context/ThemeContext';
import styles from './ResultViewer.module.css';

export default function ResultViewer({ result, onDownload }) {
  // Preview State
  const [previewContent, setPreviewContent] = useState(null);
  const [fullContent, setFullContent] = useState(null); // Store full content for "Load More"
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [isTruncated, setIsTruncated] = useState(false);

  const PREVIEW_LIMIT = 200000; // 200KB before truncation

  // Reset preview state when job_id changes (new result)
  const { job_id } = result || {};
  useEffect(() => {
    setPreviewContent(null);
    setFullContent(null);
    setShowPreview(false);
    setIsTruncated(false);
  }, [job_id]);

  // Theme context available if needed
  useTheme();

  const { metadata, stats = {} } = result || {};

  // MOVED: Copy Feedback State moved up to be unconditional
  const [copiedId, setCopiedId] = useState(null);

  if (!result || !result.success) return null;

  const handlePreview = async () => {
    if (showPreview) {
      setShowPreview(false);
      return;
    }

    setShowPreview(true);
    if (previewContent) return; // Already fetched

    setIsPreviewLoading(true);
    try {
      const url = getJobDownloadUrl(job_id, 'txt');
      const res = await fetch(url);
      const text = await res.text();
      setFullContent(text);

      // Only truncate if over 200KB
      if (text.length > PREVIEW_LIMIT) {
        setPreviewContent(text.substring(0, PREVIEW_LIMIT));
        setIsTruncated(true);
      } else {
        setPreviewContent(text);
        setIsTruncated(false);
      }
    } catch {
      setPreviewContent("Failed to load preview.");
    } finally {
      setIsPreviewLoading(false);
    }
  };


  const handleCopy = async (id, appName, url = null) => {
    let textToCopy = fullContent || previewContent;

    if (!textToCopy) {
      try {
        const fetchUrl = getJobDownloadUrl(job_id, 'txt');
        const res = await fetch(fetchUrl);
        textToCopy = await res.text();
      } catch {
        alert('Failed to load content for copying.');
        return;
      }
    }

    await navigator.clipboard.writeText(textToCopy);
    setCopiedId(id);

    // Clear feedback after 2s
    setTimeout(() => setCopiedId(null), 2000);

    // Optional: Open external URL
    if (url) {
      setTimeout(() => window.open(url, '_blank'), 500);
    }
  };

  return (
    <div className="card">
      <div className={styles.headerRow}>
        <h2 style={{ fontSize: '20px', color: 'var(--color-success)', display: 'flex', alignItems: 'center', fontWeight: '700', margin: 0 }}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" style={{ marginRight: '12px' }}>
            <polyline points="20 6 9 17 4 12" />
          </svg>
          Job Completed
        </h2>
        <div className={styles.actionButtons}>
          <button onClick={handlePreview} className="btn" style={{
            background: 'var(--color-primary)',
            border: 'none',
            color: 'var(--color-button-text)',
            fontSize: '13px',
            fontWeight: '700'
          }}>
            {showPreview ? 'Hide Preview' : 'Show Preview'}
          </button>

          <button onClick={() => onDownload('txt')} className="btn" style={{
            background: 'transparent',
            border: '1px solid var(--color-border)',
            color: 'var(--color-text)',
            fontSize: '13px',
            fontWeight: '500'
          }}>
            Download .txt
          </button>
          <button onClick={() => onDownload('toon')} className="btn" style={{
            background: 'transparent',
            border: '1px solid var(--color-border)',
            color: 'var(--color-text)',
            fontSize: '13px',
            fontWeight: '500'
          }}>
            Download .toon
          </button>
          <button
            onClick={() => handleCopy('main')}
            className="btn"
            style={{
              background: copiedId === 'main' ? 'var(--color-success)' : 'var(--color-primary)',
              color: 'var(--color-button-text)',
              fontWeight: '600',
              border: 'none',
              minWidth: '140px'
            }}
          >
            {copiedId === 'main' ? '✓ Copied!' : 'Copy to Clipboard'}
          </button>
        </div>
      </div>

      {/* Export to LLM buttons */}
      <div className={styles.exportSection}>
        <span style={{ fontSize: '13px', color: 'var(--color-text-secondary)', display: 'flex', alignItems: 'center', marginRight: '8px' }}>Export to:</span>
        <button onClick={() => handleCopy('gpt', 'ChatGPT', 'https://chat.openai.com')} className="btn" style={{ background: copiedId === 'gpt' ? 'var(--color-success)' : '#10a37f', color: 'white', fontSize: '12px', padding: '6px 12px', border: 'none', transition: 'background 0.2s' }}>
          {copiedId === 'gpt' ? '✓ Copied' : 'ChatGPT'}
        </button>
        <button onClick={() => handleCopy('claude', 'Claude', 'https://claude.ai')} className="btn" style={{ background: copiedId === 'claude' ? 'var(--color-success)' : '#d97706', color: 'white', fontSize: '12px', padding: '6px 12px', border: 'none', transition: 'background 0.2s' }}>
          {copiedId === 'claude' ? '✓ Copied' : 'Claude'}
        </button>
        <button onClick={() => handleCopy('gemini', 'Gemini', 'https://gemini.google.com')} className="btn" style={{ background: copiedId === 'gemini' ? 'var(--color-success)' : '#4285f4', color: 'white', fontSize: '12px', padding: '6px 12px', border: 'none', transition: 'background 0.2s' }}>
          {copiedId === 'gemini' ? '✓ Copied' : 'Gemini'}
        </button>
        <button onClick={() => handleCopy('perplexity', 'Perplexity', 'https://www.perplexity.ai')} className="btn" style={{ background: copiedId === 'perplexity' ? 'var(--color-success)' : '#6366f1', color: 'white', fontSize: '12px', padding: '6px 12px', border: 'none', transition: 'background 0.2s' }}>
           {copiedId === 'perplexity' ? '✓ Copied' : 'Perplexity'}
        </button>
      </div>

      <div className={styles.resultBody}>
        <div style={{ marginBottom: '32px' }}>
          <h3 style={{ fontSize: '20px', margin: '0 0 8px 0', color: 'var(--color-text)', fontWeight: '600' }}>{metadata?.title || 'Unknown Resource'}</h3>
          <p style={{ margin: 0, fontSize: '14px', color: 'var(--color-text-secondary)', wordBreak: 'break-all' }}>
            <a href={metadata?.url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--color-primary)' }}>{metadata?.url}</a>
          </p>
        </div>

        <div className={styles.statsGrid}>
          <div className={styles.statCard}>
            <strong className={styles.statLabel}>Notebooks</strong>
            <span className={styles.statValue}>{stats?.total_requested || 0}</span>
          </div>
          <div className={styles.statCard}>
            <strong className={styles.statLabel}>Processed</strong>
            <span className={styles.statValue} style={{ color: 'var(--color-success)' }}>{stats?.successful_downloads || 0}</span>
          </div>
          <div className={styles.statCard}>
            <strong className={styles.statLabel}>Time</strong>
            <span className={styles.statValue}>{stats.elapsed_time !== undefined ? stats.elapsed_time.toFixed(2) + 's' : '-'}</span>
          </div>
        </div>

        {/* Preview Section */}
        {showPreview && (
          <div style={{ marginTop: '32px', borderTop: '1px solid var(--color-border)', paddingTop: '24px' }}>
            <div className={styles.previewTop}>
              <h4 style={{ fontSize: '14px', color: 'var(--color-text-secondary)', textTransform: 'uppercase', margin: 0 }}>File Preview</h4>
              {previewContent && !isPreviewLoading && (
                <span style={{
                  fontSize: '12px',
                  padding: '4px 8px',
                  borderRadius: '12px',
                  background: 'var(--color-button)',
                  color: 'var(--color-button-text)',
                  fontWeight: '600'
                }}>
                  ~{Math.round(previewContent.length / 4).toLocaleString()} Tokens
                </span>
              )}
            </div>

            {isPreviewLoading ? (
              <div style={{ padding: '20px', textAlign: 'center', color: 'var(--color-text-secondary)' }}>Loading preview...</div>
            ) : (
              <div className={styles.codeContainer}>
                <pre className={styles.codePre}>
                  {previewContent || "Click 'Terminal Preview' to load content"}
                </pre>
                {isTruncated && (
                  <div style={{ padding: '16px', textAlign: 'center', borderTop: '1px solid var(--color-border)' }}>
                    <button
                      onClick={() => { setPreviewContent(fullContent); setIsTruncated(false); }}
                      className="btn"
                      style={{ background: 'var(--color-primary)', color: 'white', padding: '8px 24px' }}
                    >
                      Load Full Content ({Math.round(fullContent.length / 1024)}KB)
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
