import React, { useState, useMemo } from 'react';
import styles from './ResultViewer.module.css';

import { toast } from 'sonner';

export default function ResultViewer({ result, onDownload }) {
  const [copied, setCopied] = useState(false);
  const [showFull, setShowFull] = useState(false);

  // ... (keep constants)

  const PREVIEW_LIMIT = 50000;

  const { metadata, formatted_output, toon_content } = result || {};
  const content = toon_content || formatted_output;

  // ... (keep useMemos)

  const { fullContent, isTruncated } = useMemo(() => {
    if (!content) {
      return { fullContent: null, isTruncated: false };
    }

    const isTrunc = content.length > PREVIEW_LIMIT;
    return {
      fullContent: content,
      isTruncated: isTrunc
    };
  }, [content]);

  const previewContent = useMemo(() => {
    if (!fullContent) return null;
    if (showFull || !isTruncated) return fullContent;
    return fullContent.substring(0, PREVIEW_LIMIT);
  }, [fullContent, showFull, isTruncated]);


  if (!result || !result.success) return null;

  const handleCopy = async () => {
    const textToCopy = fullContent || content;
    if (!textToCopy) return;

    try {
      await navigator.clipboard.writeText(textToCopy);
      setCopied(true);
      toast.success('Context copied to clipboard!', {
        description: `${Math.round(textToCopy.length / 1024)}KB ready for LLM.`
      });
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error('Failed to copy', {
        description: 'Please use HTTPS or copy manually.'
      });
    }
  };

  const handleLoadMore = () => {
    setShowFull(true);
  };

  const tokenCount = fullContent ? Math.round(fullContent.length / 4) : 0;

  return (
    <div className="card">
      <div className={styles.headerRow}>
        <h2 style={{ fontSize: '20px', color: 'var(--color-success)', display: 'flex', alignItems: 'center', fontWeight: '700', margin: 0 }}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" style={{ marginRight: '12px' }}>
            <polyline points="20 6 9 17 4 12" />
          </svg>
          Context Ready
        </h2>
        <div className={styles.actionButtons}>
          <button
            onClick={onDownload}
            className="btn"
            style={{
              background: 'transparent',
              border: '1px solid var(--color-border)',
              color: 'var(--color-text)',
              fontSize: '13px',
              fontWeight: '500',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="7 10 12 15 17 10"/>
              <line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
            Download .toon
          </button>
          <button
            onClick={handleCopy}
            className="btn"
            style={{
              background: copied ? 'var(--color-success)' : 'var(--color-primary)',
              color: 'var(--color-button-text)',
              fontWeight: '600',
              border: 'none',
              minWidth: '160px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px'
            }}
          >
            {copied ? (
              <>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
                Copied!
              </>
            ) : (
              <>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                  <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                </svg>
                Copy Context
              </>
            )}
          </button>
        </div>
      </div>

      <div className={styles.resultBody}>
        <div style={{ marginBottom: '20px' }}>
          <h3 style={{ fontSize: '18px', margin: '0 0 8px 0', color: 'var(--color-text)', fontWeight: '600' }}>
            {metadata?.title || 'Competition Context'}
          </h3>
          <p style={{ margin: 0, fontSize: '13px', color: 'var(--color-text-secondary)', wordBreak: 'break-all' }}>
            <a href={metadata?.url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--color-primary)' }}>
              {metadata?.url}
            </a>
          </p>
        </div>

        {/* Preview Section with Token Count */}
        <div style={{ borderTop: '1px solid var(--color-border)', paddingTop: '16px' }}>
          <div className={styles.previewTop} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <h4 style={{ fontSize: '13px', color: 'var(--color-text-secondary)', textTransform: 'uppercase', margin: 0, display: 'flex', alignItems: 'center', gap: '6px' }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
              </svg>
              Preview
            </h4>
            <span style={{
              fontSize: '12px',
              padding: '4px 10px',
              borderRadius: '12px',
              background: 'var(--color-primary)',
              color: 'white',
              fontWeight: '600'
            }}>
              ~{tokenCount.toLocaleString()} tokens
            </span>
          </div>

          <div className={styles.codeContainer}>
            <pre className={styles.codePre} style={showFull ? { maxHeight: 'none' } : {}}>
              {previewContent !== null && previewContent !== undefined ? previewContent : (
                  <span style={{ color: 'var(--color-text-secondary)', fontStyle: 'italic' }}>
                      {metadata ? "Preview not available for this resource." : "Loading..."}
                  </span>
              )}
            </pre>
            {isTruncated && !showFull && (
              <div style={{ padding: '16px', textAlign: 'center', borderTop: '1px solid var(--color-border)' }}>
                <button
                  onClick={handleLoadMore}
                  className="btn"
                  style={{ background: 'var(--color-primary)', color: 'white', padding: '8px 24px' }}
                >
                  Load More ({Math.round((fullContent?.length || 0) / 1024)}KB total)
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
