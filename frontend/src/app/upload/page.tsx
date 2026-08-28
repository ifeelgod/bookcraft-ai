'use client';

import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, FileText, CheckCircle2, XCircle, Loader2, ArrowLeft } from 'lucide-react';
import Link from 'next/link';
import toast from 'react-hot-toast';
import { uploadFile, pollJobStatus } from '@/lib/api';
import type { JobStatus } from '@/types/api';

type UploadState = 'idle' | 'uploading' | 'polling' | 'done' | 'error';

export default function UploadPage() {
  const [state, setState] = useState<UploadState>('idle');
  const [jobId, setJobId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [statusMsg, setStatusMsg] = useState('');
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [errorMsg, setErrorMsg] = useState('');

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    const file = acceptedFiles[0];
    if (!file) return;

    setState('uploading');
    setProgress(0);
    setErrorMsg('');

    try {
      const res = await uploadFile(file);
      setJobId(res.job_id);
      toast.success(`File "${file.name}" uploaded. Parsing started.`);
      setState('polling');

      // Poll for status
      await pollJobStatus(
        res.job_id,
        (status: JobStatus) => {
          setProgress(status.progress);
          setStatusMsg(status.message);
          if (status.status === 'completed') {
            setState('done');
            setResult(status.result ?? null);
            toast.success('Document parsed successfully!');
          } else if (status.status === 'failed') {
            setState('error');
            setErrorMsg(status.error ?? 'Unknown error');
            toast.error('Parsing failed.');
          }
        }
      );
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Upload failed';
      setState('error');
      setErrorMsg(message);
      toast.error(message);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    onDrop,
    accept: {
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'application/pdf': ['.pdf'],
    },
    maxFiles: 1,
    disabled: state === 'uploading' || state === 'polling',
  });

  return (
    <div className="min-h-screen bg-gray-50 px-4 py-12">
      <div className="mx-auto max-w-2xl">
        {/* Header */}
        <div className="mb-8">
          <Link href="/" className="inline-flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700 mb-4">
            <ArrowLeft className="h-4 w-4" /> Back to home
          </Link>
          <h1 className="text-3xl font-bold text-gray-900">Upload Manuscript</h1>
          <p className="text-gray-500 mt-2">
            Upload a <code className="text-xs bg-gray-100 px-1 py-0.5 rounded">.docx</code> or{' '}
            <code className="text-xs bg-gray-100 px-1 py-0.5 rounded">.pdf</code> file to get started.
          </p>
        </div>

        {/* Drop zone */}
        <div
          {...getRootProps()}
          className={`card cursor-pointer border-2 border-dashed transition-colors text-center py-16 ${
            isDragActive && !isDragReject
              ? 'border-brand-500 bg-brand-50'
              : isDragReject
              ? 'border-red-400 bg-red-50'
              : 'border-gray-300 hover:border-brand-400 hover:bg-brand-50/30'
          } ${state === 'uploading' || state === 'polling' ? 'opacity-60 cursor-not-allowed' : ''}`}
        >
          <input {...getInputProps()} />
          <Upload className="mx-auto h-12 w-12 text-gray-400 mb-4" />
          {isDragActive && !isDragReject && (
            <p className="text-brand-600 font-semibold">Drop your file here…</p>
          )}
          {isDragReject && (
            <p className="text-red-600 font-semibold">Only .docx and .pdf files are accepted.</p>
          )}
          {!isDragActive && (
            <>
              <p className="text-gray-700 font-medium">Drag &amp; drop your manuscript here</p>
              <p className="text-sm text-gray-500 mt-1">or click to browse</p>
              <p className="text-xs text-gray-400 mt-3">.docx · .pdf · Max 50 MB</p>
            </>
          )}
        </div>

        {/* Status panel */}
        {state !== 'idle' && (
          <div className="card mt-6">
            {/* Uploading */}
            {state === 'uploading' && (
              <div className="flex items-center gap-3 text-gray-700">
                <Loader2 className="h-5 w-5 animate-spin text-brand-600" />
                <span>Uploading file…</span>
              </div>
            )}

            {/* Polling */}
            {state === 'polling' && (
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2 text-sm text-gray-700">
                    <Loader2 className="h-4 w-4 animate-spin text-brand-600" />
                    <span>{statusMsg || 'Processing…'}</span>
                  </div>
                  <span className="text-sm font-medium text-brand-600">{progress}%</span>
                </div>
                <div className="h-2 w-full rounded-full bg-gray-200">
                  <div
                    className="h-2 rounded-full bg-brand-600 transition-all duration-500"
                    style={{ width: `${progress}%` }}
                  />
                </div>
                {jobId && (
                  <p className="text-xs text-gray-400 mt-2">Job ID: {jobId}</p>
                )}
              </div>
            )}

            {/* Done */}
            {state === 'done' && (
              <div>
                <div className="flex items-center gap-2 text-green-700 mb-4">
                  <CheckCircle2 className="h-5 w-5" />
                  <span className="font-semibold">Parsing complete!</span>
                </div>
                {result && (
                  <details className="mt-2">
                    <summary className="text-sm text-gray-500 cursor-pointer hover:text-gray-700">
                      View DocumentAST
                    </summary>
                    <pre className="mt-3 text-xs bg-gray-900 text-green-400 rounded-lg p-4 overflow-auto max-h-72">
                      {JSON.stringify(result, null, 2)}
                    </pre>
                  </details>
                )}
                <div className="mt-4 flex gap-3">
                  <Link href={`/editor?jobId=${jobId}`} className="btn-primary text-sm">
                    <FileText className="h-4 w-4" /> Open in Editor
                  </Link>
                  <button
                    onClick={() => { setState('idle'); setResult(null); setJobId(null); }}
                    className="btn-secondary text-sm"
                  >
                    Upload Another
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
                <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{errorMsg}</p>
                <button
                  onClick={() => { setState('idle'); setErrorMsg(''); }}
                  className="btn-secondary text-sm mt-4"
                >
                  Try Again
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
