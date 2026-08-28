/**
 * API client — thin wrappers around fetch/axios for the BookCraft AI backend.
 */
import type { DocumentAST, JobStatus, UploadResponse, CompileResponse } from '@/types/api';

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

// ────────────────────────────────────────────────────────────
// Upload
// ────────────────────────────────────────────────────────────

export async function uploadFile(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append('file', file);

  const res = await fetch(`${BASE_URL}/api/upload`, {
    method: 'POST',
    body: form,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Upload failed (${res.status})`);
  }

  return res.json();
}

// ────────────────────────────────────────────────────────────
// Status polling
// ────────────────────────────────────────────────────────────

export async function getJobStatus(jobId: string): Promise<JobStatus> {
  const res = await fetch(`${BASE_URL}/api/status/${jobId}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Status check failed (${res.status})`);
  }
  return res.json();
}

/**
 * Polls a job every `intervalMs` until it reaches `completed` or `failed`.
 * Calls `onUpdate` on each poll tick.
 */
export async function pollJobStatus(
  jobId: string,
  onUpdate: (status: JobStatus) => void,
  intervalMs = 1500,
  timeoutMs = 300_000,
): Promise<JobStatus> {
  const deadline = Date.now() + timeoutMs;

  while (Date.now() < deadline) {
    const status = await getJobStatus(jobId);
    onUpdate(status);

    if (status.status === 'completed' || status.status === 'failed') {
      return status;
    }

    await new Promise((r) => setTimeout(r, intervalMs));
  }

  throw new Error('Job timed out after 5 minutes.');
}

// ────────────────────────────────────────────────────────────
// Fetch AST
// ────────────────────────────────────────────────────────────

export async function getAst(jobId: string): Promise<{ job_id: string; ast: DocumentAST; summary: any }> {
  const res = await fetch(`${BASE_URL}/api/ast/${jobId}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to fetch AST (${res.status})`);
  }
  return res.json();
}

// ────────────────────────────────────────────────────────────
// Compile
// ────────────────────────────────────────────────────────────

export async function compileDocument(ast: DocumentAST): Promise<CompileResponse> {
  const res = await fetch(`${BASE_URL}/api/compile`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(ast),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Compile failed (${res.status})`);
  }

  return res.json();
}
