import React, { useState, useEffect, useRef, useCallback } from 'react';
import InputForm from './components/InputForm';

const ResultViewer = React.lazy(() => import('./components/ResultViewer'));
import Header from './components/Header';
import Footer from './components/Footer';
import ErrorBoundary from './components/ErrorBoundary';
import { ingestContext } from './services/api';
import { ThemeProvider } from './context/ThemeContext';
import './App.css';
import { Toaster } from 'sonner';
import LoadingState from './components/LoadingState';

function IngestApp() { // Main content within Provider
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const resultRef = useRef(null);
  const processRef = useRef(null);

  const handleIngest = useCallback(async (payload) => {
    setIsSubmitting(true);
    setError('');
    setResult(null);

    try {
      let res = await ingestContext(payload);

      // Poll if processing
      if (res.success && res.status === 'processing') {
        const MAX_RETRIES = 30; // 30 * 2s = 60s max wait
        let retries = 0;

        while (res.success && res.status === 'processing' && retries < MAX_RETRIES) {
          await new Promise(resolve => setTimeout(resolve, 2000));
          retries++;

          // Re-fetch using the same slug/url logic
          // Note: ingestContext handles the URL parsing again, which is fine
          res = await ingestContext(payload);
        }
      }

      if (res.success && res.status === 'completed') {
        setResult(res);
      } else if (res.success && res.status === 'failed') {
        setError(res.message || 'Ingestion failed on server.');
      } else {
        setError(res.error || res.message || 'Failed to ingest competition');
      }
    } catch (err) {
      setError(err.message || 'An unexpected error occurred');
    } finally {
      setIsSubmitting(false);
    }
  }, []);

  // Auto-scroll to results when complete
  useEffect(() => {
    if (result && resultRef.current) {
      resultRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [result]);

  // Auto-scroll when ingestion starts
  useEffect(() => {
    if (isSubmitting && processRef.current) {
      processRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [isSubmitting]);

  const handleDownload = useCallback(() => {
    const content = result?.toon_content || result?.formatted_output;
    if (!content) return;

    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `kaggle-context-${result.metadata?.id?.replace('/', '-') || result.slug || 'competition'}.toon`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [result]);

  // Enhanced Magic URL support: Detect Kaggle paths from URL and auto-ingest
  const [initialUrl] = useState(() => {
    const path = window.location.pathname;
    const kagglePathRegex = /^\/(competitions|datasets|code|kernels|c)\/[a-z0-9.-]+/i;

    if (kagglePathRegex.test(path)) {
      // Normalize path to Kaggle URL
      return `https://www.kaggle.com${path}`;
    }
    return '';
  });

  // Auto-ingest effect with safety checks
  useEffect(() => {
    if (!initialUrl) return;

    // Small delay to allow AuthProvider to initialize apiKey
    const timer = setTimeout(() => {
      console.log("🪄 Magic URL detected, auto-ingesting:", initialUrl);
      handleIngest({
        url: initialUrl,
        top_n: 3
      });
    }, 800);

    return () => clearTimeout(timer);
  }, [initialUrl, handleIngest]); // Run when initialUrl or handleIngest changes

  const currentStatusObject = isSubmitting ? { status: 'processing' } : null;

  return (
    <>
      <Header />

      <main className="container" id="main-content">

        <InputForm
          onSubmit={handleIngest}
          isLoading={isSubmitting}
          status={currentStatusObject}
          initialUrl={initialUrl}
        />

        {/* Loading/Error/Result Section */}
        <div ref={processRef}>
          {/* Error State */}
          {error && (
            <div className="card" style={{ borderColor: 'var(--color-error)', backgroundColor: 'var(--color-surface)', maxWidth: '800px', margin: '0 auto 20px auto', padding: '24px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
                <span style={{ fontSize: '24px' }}>⚠️</span>
                <h3 style={{ color: 'var(--color-error)', fontSize: '1.4rem', margin: 0 }}>
                  {error.includes('401') || error.includes('403') || error.includes('X-API-Key') ? 'Authentication Required' : (error.includes('429') ? 'Shared Limit Reached' : 'Ingestion Failed')}
                </h3>
              </div>

              {(error.includes('429') || error.includes('Too Many Requests')) ? (
                <div className="quota-guide" style={{ textAlign: 'left' }}>
                  <p style={{ marginBottom: '16px', fontSize: '1.1rem' }}>
                    The shared server has hit Kaggle's hourly rate limit. <br />
                    <strong>Don't worry! You can still ingest this competition using your own credentials.</strong>
                  </p>

                  <div style={{ backgroundColor: 'rgba(255,255,255,0.05)', padding: '16px', borderRadius: '8px', border: '1px solid var(--color-border)' }}>
                    <h4 style={{ margin: '0 0 12px 0', color: 'var(--color-primary)' }}>🚀 How to fix this in 30 seconds:</h4>
                    <ol style={{ paddingLeft: '24px', lineHeight: '1.6', marginBottom: '16px' }}>
                      <li>Go to your <strong><a href="https://www.kaggle.com/settings/account" target="_blank" rel="noopener noreferrer" style={{ textDecoration: 'underline', color: 'var(--color-primary)' }}>Kaggle Account Settings</a></strong>.</li>
                      <li>Scroll down to the <strong>API</strong> section.</li>
                      <li>Click <strong>Create New Token</strong> (this downloads a <code>kaggle.json</code> file).</li>
                      <li>Come back here and click <strong>"Add Private Credentials"</strong> above.</li>
                      <li>Upload your <code>kaggle.json</code> and try again!</li>
                    </ol>
                    <p style={{ fontSize: '0.9rem', opacity: 0.8, margin: 0 }}>
                      🔒 Your credentials are used <strong>only for this request</strong> and are never stored on our servers.
                    </p>
                  </div>
                </div>
              ) : (
                <pre style={{ whiteSpace: 'pre-wrap', fontSize: '13px', color: 'var(--color-text)', backgroundColor: 'rgba(0,0,0,0.2)', padding: '12px', borderRadius: '4px' }}>{error}</pre>
              )}
            </div>
          )}

          {/* Loading State */}
          {isSubmitting && <LoadingState />}
        </div>

        {/* Success / Result State */}


        {/* Success / Result State */}
        <React.Suspense fallback={<LoadingState />}>
          <div ref={resultRef}>
            {result && <ResultViewer result={result} onDownload={handleDownload} />}
          </div>
        </React.Suspense>

      </main>
      <Footer />
    </>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider>
        <Toaster position="top-center" richColors closeButton theme="system" />
        <IngestApp />
      </ThemeProvider>
    </ErrorBoundary>
  );
}
