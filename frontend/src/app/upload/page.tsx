'use client';

import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import {
  Upload,
  FileText,
  CheckCircle2,
  XCircle,
  Loader2,
  ArrowLeft,
  Sparkles,
  ShieldAlert,
  Info,
} from 'lucide-react';
import Link from 'next/link';
import toast from 'react-hot-toast';
import { uploadFile, pollJobStatus } from '@/lib/api';
import { useAuth } from '@/lib/authStore';
import type { JobStatus, LeadFormData } from '@/types/api';
import LeadCaptureModal from '@/components/LeadCaptureModal';

type UploadState = 'idle' | 'uploading' | 'polling' | 'done' | 'error';

export default function UploadPage() {
  const { isPro, tier, token, email: authEmail, name: authName } = useAuth();
  const [state, setState] = useState<UploadState>('idle');
  const [jobId, setJobId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [statusMsg, setStatusMsg] = useState('');
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [isTruncated, setIsTruncated] = useState(false);

  // Lead modal state
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSubmittingLead, setIsSubmittingLead] = useState(false);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const file = acceptedFiles[0];
    if (!file) return;

    if (isPro) {
      // Pro users upload immediately without gating
      handleDirectProUpload(file);
      return;
    }

    // Open Lead Capture Interstitial Modal for demo users
    setPendingFile(file);
    setIsModalOpen(true);
  }, [isPro, token, authEmail, authName]);

  const handleDirectProUpload = async (file: File) => {
    setState('uploading');
    setProgress(0);
    setErrorMsg('');
    setIsTruncated(false);

    try {
      const res = await uploadFile(
        file,
        {
          name: authName || 'Pro Author',
          email: authEmail || 'pro@bookcraft.ai',
          marketingConsent: true,
          tier: tier || 'pro',
        },
        token || undefined,
      );
      setJobId(res.job_id);
      setIsTruncated(false);
      setState('polling');

      await pollJobStatus(res.job_id, (status: JobStatus) => {
        setProgress(status.progress);
        setStatusMsg(status.message);
        if (status.status === 'completed') {
          setState('done');
          setResult(status.result ?? null);
          toast.success('Pro manuscript parsed with zero page limits!');
        } else if (status.status === 'failed') {
          setState('error');
          setErrorMsg(status.error ?? 'Unknown error');
          toast.error('Parsing failed.');
        }
      });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Upload failed';
      setState('error');
      setErrorMsg(message);
      toast.error(message);
    }
  };

  const handleLeadSubmit = async (leadData: LeadFormData) => {
    if (!pendingFile) return;

    setIsSubmittingLead(true);
    setState('uploading');
    setProgress(0);
    setErrorMsg('');
    setIsTruncated(false);

    try {
      const res = await uploadFile(pendingFile, leadData, token || undefined);
      setJobId(res.job_id);
      setIsTruncated(Boolean(res.is_truncated));
      setIsModalOpen(false);
      setIsSubmittingLead(false);

      if (res.is_truncated) {
        toast('Manuscript exceeds 15 pages — demo preview capped at 15 pages.', {
          icon: 'ℹ️',
          duration: 6000,
        });
      } else {
        toast.success(`File "${pendingFile.name}" uploaded. Parsing started.`);
      }

      setState('polling');

      // Poll for status
      await pollJobStatus(res.job_id, (status: JobStatus) => {
        setProgress(status.progress);
        setStatusMsg(status.message);
        if (status.status === 'completed') {
          setState('done');
          setResult(status.result ?? null);
          toast.success('Document parsed and formatted successfully!');
        } else if (status.status === 'failed') {
          setState('error');
          setErrorMsg(status.error ?? 'Unknown error');
          toast.error('Parsing failed.');
        }
      });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Upload failed';
      setState('error');
      setErrorMsg(message);
      setIsSubmittingLead(false);
      setIsModalOpen(false);
      toast.error(message);
    }
  };

  const handleModalCancel = () => {
    setIsModalOpen(false);
    setPendingFile(null);
    setState('idle');
  };

  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    onDrop,
    accept: {
      'application/msword': ['.doc'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'application/pdf': ['.pdf'],
      'text/markdown': ['.md'],
    },
    maxFiles: 1,
    disabled: state === 'uploading' || state === 'polling' || isModalOpen,
  });

  return (
    <div className="min-h-screen bg-gray-50 px-4 py-12">
      <div className="mx-auto max-w-2xl">
        {/* Header */}
        <div className="mb-8">
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700 mb-4 transition-colors"
          >
            <ArrowLeft className="h-4 w-4" /> Back to home
          </Link>
          <div className="flex items-center justify-between">
            <h1 className="text-3xl font-bold text-gray-900">Upload Manuscript</h1>
            {isPro ? (
              <Link
                href="/checkout"
                className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 border border-amber-200 px-3 py-1 text-xs font-semibold text-amber-700 hover:bg-amber-100 transition-colors"
              >
                <Sparkles className="h-3.5 w-3.5 text-amber-500" />
                <span>{tier?.toUpperCase()} Active (Unlimited Pages)</span>
              </Link>
            ) : (
              <Link
                href="/checkout"
                className="inline-flex items-center gap-1.5 rounded-full bg-brand-50 border border-brand-200 px-3 py-1 text-xs font-semibold text-brand-700 hover:bg-brand-100 transition-colors"
              >
                <Sparkles className="h-3.5 w-3.5" /> 15-Page Free Demo • Upgrade
              </Link>
            )}
          </div>
          <p className="text-gray-500 mt-2">
            Upload a <code className="text-xs bg-gray-100 px-1 py-0.5 rounded">.doc</code>,{' '}
            <code className="text-xs bg-gray-100 px-1 py-0.5 rounded">.docx</code>,{' '}
            <code className="text-xs bg-gray-100 px-1 py-0.5 rounded">.pdf</code>, or{' '}
            <code className="text-xs bg-gray-100 px-1 py-0.5 rounded">.md</code> manuscript to
            generate a publication-ready book preview.
          </p>
        </div>

        {/* Drop zone */}
        <div
          {...getRootProps()}
          className={`card cursor-pointer border-2 border-dashed transition-all text-center py-16 ${
            isDragActive && !isDragReject
              ? 'border-brand-500 bg-brand-50 shadow-inner'
              : isDragReject
              ? 'border-red-400 bg-red-50'
              : 'border-gray-300 hover:border-brand-400 hover:bg-brand-50/30'
          } ${
            state === 'uploading' || state === 'polling' || isModalOpen
              ? 'opacity-60 cursor-not-allowed'
              : ''
          }`}
        >
          <input {...getInputProps()} />
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-gray-100 text-gray-500">
            <Upload className="h-7 w-7" />
          </div>
          {isDragActive && !isDragReject && (
            <p className="text-brand-600 font-semibold text-lg">Drop your manuscript here</p>
          )}
          {isDragReject && (
            <p className="text-red-600 font-semibold">
              Only .doc, .docx, .pdf, and .md files are accepted.
            </p>
          )}
          {!isDragActive && (
            <>
              <p className="text-gray-900 font-semibold text-base">
                Drag &amp; drop your manuscript here
              </p>
              <p className="text-sm text-gray-500 mt-1">or click to browse from your computer</p>
              <div className="mt-4 flex items-center justify-center gap-2 text-xs text-gray-400">
                <span>DOCX</span>
                <span>•</span>
                <span>PDF</span>
                <span>•</span>
                <span>Markdown</span>
                <span>•</span>
                <span>Max 50 MB</span>
              </div>
            </>
          )}
        </div>

        {/* Demo Notice Banner */}
        <div className="mt-4 rounded-xl bg-blue-50/70 border border-blue-100 p-3.5 flex items-start gap-3">
          <Info className="h-5 w-5 text-blue-600 shrink-0 mt-0.5" />
          <p className="text-xs text-blue-900 leading-relaxed">
            <span className="font-semibold">Free Demo Version:</span> Automatically structures the
            first 15 pages of your book with AI chapter detection and typography. Full manuscripts
            can be unlocked inside the editor.
          </p>
        </div>

        {/* Status panel */}
        {state !== 'idle' && (
          <div className="card mt-6 border border-gray-200 shadow-md">
            {/* Uploading */}
            {state === 'uploading' && (
              <div className="flex items-center gap-3 text-gray-700 py-2">
                <Loader2 className="h-5 w-5 animate-spin text-brand-600" />
                <span className="font-medium">Uploading and validating manuscript…</span>
              </div>
            )}

            {/* Polling */}
            {state === 'polling' && (
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2 text-sm text-gray-800">
                    <Loader2 className="h-4 w-4 animate-spin text-brand-600" />
                    <span className="font-medium">{statusMsg || 'Processing manuscript…'}</span>
                  </div>
                  <span className="text-sm font-bold text-brand-600">{progress}%</span>
                </div>
                <div className="h-2.5 w-full rounded-full bg-gray-200 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-brand-600 transition-all duration-500"
                    style={{ width: `${progress}%` }}
                  />
                </div>
                <div className="mt-3 flex items-center justify-between text-xs text-gray-400">
                  <span>Job ID: {jobId}</span>
                  {isTruncated && (
                    <span className="text-amber-600 font-medium bg-amber-50 px-2 py-0.5 rounded">
                      Demo: Capped to 15 pages
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* Done */}
            {state === 'done' && (
              <div>
                <div className="flex items-center gap-2 text-green-700 mb-2">
                  <CheckCircle2 className="h-5 w-5" />
                  <span className="font-bold text-base">Manuscript Formatted Successfully!</span>
                </div>
                <p className="text-xs text-gray-500 mb-4">
                  Your 15-page publication-ready preview is compiled and ready in the live editor.
                </p>

                {result && (
                  <details className="mb-4">
                    <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-700">
                      View Parsed DocumentAST Structure
                    </summary>
                    <pre className="mt-2 text-xs bg-gray-900 text-green-400 rounded-lg p-4 overflow-auto max-h-56">
                      {JSON.stringify(result, null, 2)}
                    </pre>
                  </details>
                )}

                <div className="flex flex-wrap gap-3">
                  <Link
                    href={`/editor?jobId=${jobId}`}
                    className="btn-primary text-sm flex items-center gap-2 shadow-sm"
                  >
                    <FileText className="h-4 w-4" /> Open in Editor Preview
                  </Link>
                  <button
                    onClick={() => {
                      setState('idle');
                      setResult(null);
                      setJobId(null);
                      setPendingFile(null);
                    }}
                    className="btn-secondary text-sm"
                  >
                    Upload Another Manuscript
                  </button>
                </div>
              </div>
            )}

            {/* Error */}
            {state === 'error' && (
              <div>
                <div className="flex items-center gap-2 text-red-700 mb-2">
                  <XCircle className="h-5 w-5" />
                  <span className="font-semibold">Something went wrong</span>
                </div>
                <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2 border border-red-200">
                  {errorMsg}
                </p>
                <button
                  onClick={() => {
                    setState('idle');
                    setErrorMsg('');
                    setPendingFile(null);
                  }}
                  className="btn-secondary text-sm mt-4"
                >
                  Try Again
                </button>
              </div>
            )}
          </div>
        )}

        {/* Lead Capture Interstitial Modal */}
        <LeadCaptureModal
          isOpen={isModalOpen}
          file={pendingFile}
          onSubmit={handleLeadSubmit}
          onCancel={handleModalCancel}
          isLoading={isSubmittingLead}
        />
      </div>
    </div>
  );
}
