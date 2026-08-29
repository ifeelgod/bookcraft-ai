/**
 * API client — thin wrappers around fetch for the BookCraft AI backend.
 */
import type {
  DocumentAST,
  JobStatus,
  UploadResponse,
  CompileResponse,
  LeadFormData,
} from '@/types/api';

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

// ────────────────────────────────────────────────────────────
// Upload
// ────────────────────────────────────────────────────────────

export async function uploadFile(
  file: File,
  leadData?: LeadFormData,
  authToken?: string,
): Promise<UploadResponse> {
  const form = new FormData();
  form.append('file', file);

  if (leadData) {
    form.append('name', leadData.name);
    form.append('email', leadData.email);
    form.append('marketing_consent', String(leadData.marketingConsent));
    form.append('tier', leadData.tier || 'demo');
  }

  const headers: Record<string, string> = {};
  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`;
  }

  const res = await fetch(`${BASE_URL}/api/upload`, {
    method: 'POST',
    headers,
    body: form,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const message =
      err.detail?.message ||
      (typeof err.detail === 'string' ? err.detail : null) ||
      `Upload failed (${res.status})`;
    throw new Error(message);
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

export async function getAst(
  jobId: string,
): Promise<{ job_id: string; ast: DocumentAST; summary: any }> {
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

export async function compileDocument(
  ast: DocumentAST,
  authToken?: string,
  tier?: string,
): Promise<CompileResponse> {
  const token = authToken || (typeof window !== 'undefined' ? localStorage.getItem('bookcraft_auth_token') : null);
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  let url = `${BASE_URL}/api/compile`;
  if (tier) {
    url += `?tier=${encodeURIComponent(tier)}`;
  }

  const res = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify(ast),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Compile failed (${res.status})`);
  }

  return res.json();
}

// ────────────────────────────────────────────────────────────
// Payment & Checkout API
// ────────────────────────────────────────────────────────────

import type {
  CheckoutRequestPayload,
  CheckoutResult,
  VerifyPaymentPayload,
  VerifyPaymentResult,
  PaymentConfigResponse,
} from '@/types/api';

export async function getPaymentConfig(): Promise<PaymentConfigResponse> {
  const res = await fetch(`${BASE_URL}/api/payments/config`);
  if (!res.ok) {
    throw new Error(`Failed to load payment config (${res.status})`);
  }
  return res.json();
}

export async function createCheckoutSession(
  payload: CheckoutRequestPayload,
): Promise<CheckoutResult> {
  const res = await fetch(`${BASE_URL}/api/payments/checkout`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const message = err.detail?.message || `Checkout failed (${res.status})`;
    throw new Error(message);
  }

  return res.json();
}

export async function verifyPaymentSession(
  payload: VerifyPaymentPayload,
): Promise<VerifyPaymentResult> {
  const res = await fetch(`${BASE_URL}/api/payments/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const message = err.detail?.message || `Payment verification failed (${res.status})`;
    throw new Error(message);
  }

  return res.json();
}

