import React, { useState, useEffect } from 'react';
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';
import InputForm from './components/InputForm';
import ResultViewer from './components/ResultViewer';
import Header from './components/Header';
import Footer from './components/Footer';
import { ingestContext, pollJobStatus, getJobDownloadUrl } from './services/api';
import { ThemeProvider } from './context/ThemeContext';
import './App.css';

const queryClient = new QueryClient();

function IngestApp() { // Main content within Provider
  const [result, setResult] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // React Query for Polling
  const { data: jobStatusData } = useQuery({
    queryKey: ['jobStatus', jobId],
    queryFn: () => pollJobStatus(jobId),
    enabled: !!jobId, // Only poll if we have a job ID
    refetchInterval: (query) => {
      // Stop polling if complete or failed
      const status = query.state.data?.status;
      return (status === 'complete' || status === 'failed') ? false : 2000;
    },
    refetchIntervalInBackground: true
  });

  // Watch for completion
  useEffect(() => {
    if (jobStatusData) {
      if (jobStatusData.status === 'complete') {
        setResult({ success: true, ...jobStatusData.result, job_id: jobId });
        setJobId(null); // Stop polling by disabling query
        setIsSubmitting(false);
      } else if (jobStatusData.status === 'failed') {
        setError(jobStatusData.error || "Job failed during processing");
        setJobId(null);
        setIsSubmitting(false);
      } else if (jobStatusData.status === 'error') {
        setError(jobStatusData.error);
        setJobId(null);
        setIsSubmitting(false);
      }
    }
  }, [jobStatusData, jobId]);


  const handleIngest = async (payload) => {
    setIsSubmitting(true);
    setError('');
    setResult(null);
    setJobId(null);

    const res = await ingestContext(payload);

    if (res.success) {
      setJobId(res.job_id);
    } else {
      setError(res.error || 'Failed to submit job');
      setIsSubmitting(false);
    }
  };

  const handleDownload = (format = 'txt') => {
    if (!result || !result.job_id) return;
    const url = getJobDownloadUrl(result.job_id, format);
    window.open(url, '_blank');
  };

  const [initialUrl, setInitialUrl] = useState('');

  // Auto-ingest based on URL path
  useEffect(() => {
    const path = window.location.pathname;
    // Basic check: must have at least one segment and not be /assets or standard vite routes
    if (path && path !== '/' && !path.startsWith('/assets')) {
      const kaggleUrl = `https://www.kaggle.com${path}`;
      setInitialUrl(kaggleUrl);

      // Auto-trigger ingestion with default options
      // We use a small timeout to ensure the UI is ready
      setTimeout(() => {
        handleIngest({
          url: kaggleUrl,
          top_n: 3,
          output_format: 'toon',
          dry_run: false
        });
      }, 500);
    }
  }, []);

  const currentStatusObject = jobStatusData || (isSubmitting ? { status: 'queued' } : null);

  return (
    <>
      <Header />
      <div className="container">

        <InputForm
          onSubmit={handleIngest}
          isLoading={isSubmitting || (jobId && jobStatusData?.status !== 'complete')}
          status={currentStatusObject}
          initialUrl={initialUrl}
        />

        {/* Error State */}
        {error && (
          <div className="card" style={{ borderColor: 'var(--color-error)', backgroundColor: 'var(--color-surface)', maxWidth: '800px', margin: '0 auto 20px auto', padding: '16px' }}>
            {/* Using inline style for error background temporarily, ideally var */}
            <h3 style={{ color: 'var(--color-error)', fontSize: '1.2rem', marginBottom: '8px' }}>Ingestion Failed</h3>
            <pre style={{ whiteSpace: 'pre-wrap', fontSize: '13px', color: 'var(--color-text)' }}>{error}</pre>
          </div>
        )}

        {/* Success / Result State */}
        <ResultViewer result={result} onDownload={handleDownload} />

      </div>
      <Footer />
    </>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <IngestApp />
      </ThemeProvider>
    </QueryClientProvider>
  );
}
