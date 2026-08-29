'use client';

import React, { useState, useEffect } from 'react';
import { X, Sparkles, FileText, CheckCircle, AlertCircle, ShieldCheck } from 'lucide-react';

export interface LeadFormData {
  name: string;
  email: string;
  marketingConsent: boolean;
}

interface LeadCaptureModalProps {
  isOpen: boolean;
  file: File | null;
  onSubmit: (leadData: LeadFormData) => void;
  onCancel: () => void;
  isLoading?: boolean;
}

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function LeadCaptureModal({
  isOpen,
  file,
  onSubmit,
  onCancel,
  isLoading = false,
}: LeadCaptureModalProps) {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [marketingConsent, setMarketingConsent] = useState(true);
  const [errors, setErrors] = useState<{ name?: string; email?: string }>({});

  useEffect(() => {
    if (isOpen) {
      setErrors({});
    }
  }, [isOpen]);

  if (!isOpen || !file) return null;

  const fileSizeFormatted = (file.size / 1024 / 1024).toFixed(2) + ' MB';

  const validate = (): boolean => {
    const newErrors: { name?: string; email?: string } = {};

    if (!name.trim() || name.trim().length < 2) {
      newErrors.name = 'Please enter your full name (minimum 2 characters).';
    }

    if (!email.trim()) {
      newErrors.email = 'Email address is required.';
    } else if (!EMAIL_REGEX.test(email.trim())) {
      newErrors.email = 'Please enter a valid email address.';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    onSubmit({
      name: name.trim(),
      email: email.trim().toLowerCase(),
      marketingConsent,
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div
        className="relative w-full max-w-lg overflow-hidden rounded-2xl bg-white shadow-2xl border border-gray-100"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Top decorative gradient bar */}
        <div className="h-2 bg-gradient-to-r from-brand-600 via-indigo-600 to-purple-600" />

        {/* Close Button */}
        <button
          type="button"
          onClick={onCancel}
          disabled={isLoading}
          className="absolute top-5 right-5 text-gray-400 hover:text-gray-600 transition-colors"
          aria-label="Close"
        >
          <X className="h-5 w-5" />
        </button>

        <div className="p-6 sm:p-8">
          {/* Header */}
          <div className="flex items-center gap-3 mb-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-100 text-brand-600">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-brand-600">
                Free Demo Preview
              </span>
              <h2 className="text-xl font-bold text-gray-900">Format Your Manuscript</h2>
            </div>
          </div>

          <p className="text-sm text-gray-600 mb-6">
            Get your instant <span className="font-semibold text-gray-900">15-page publication-ready preview</span>. 
            Experience AI-driven chapter structuring, typography, and live two-page spread formatting.
          </p>

          {/* Selected File Card */}
          <div className="flex items-center gap-3 rounded-xl bg-gray-50 border border-gray-200 p-3 mb-6">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-white border border-gray-200 text-gray-700 shadow-sm">
              <FileText className="h-5 w-5" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-gray-900">{file.name}</p>
              <p className="text-xs text-gray-500">{fileSizeFormatted}</p>
            </div>
            <span className="inline-flex items-center rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-medium text-blue-700">
              15-Page Demo
            </span>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="lead-name" className="block text-sm font-medium text-gray-700 mb-1">
                Full Name <span className="text-red-500">*</span>
              </label>
              <input
                id="lead-name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Jane Austen"
                disabled={isLoading}
                className={`w-full rounded-lg border px-3.5 py-2.5 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 ${
                  errors.name
                    ? 'border-red-300 focus:border-red-500 focus:ring-red-200'
                    : 'border-gray-300 focus:border-brand-500 focus:ring-brand-100'
                }`}
              />
              {errors.name && (
                <p className="mt-1 flex items-center gap-1 text-xs text-red-600">
                  <AlertCircle className="h-3.5 w-3.5" /> {errors.name}
                </p>
              )}
            </div>

            <div>
              <label htmlFor="lead-email" className="block text-sm font-medium text-gray-700 mb-1">
                Email Address <span className="text-red-500">*</span>
              </label>
              <input
                id="lead-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="e.g. jane@example.com"
                disabled={isLoading}
                className={`w-full rounded-lg border px-3.5 py-2.5 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 ${
                  errors.email
                    ? 'border-red-300 focus:border-red-500 focus:ring-red-200'
                    : 'border-gray-300 focus:border-brand-500 focus:ring-brand-100'
                }`}
              />
              {errors.email && (
                <p className="mt-1 flex items-center gap-1 text-xs text-red-600">
                  <AlertCircle className="h-3.5 w-3.5" /> {errors.email}
                </p>
              )}
            </div>

            {/* Marketing Consent */}
            <div className="flex items-start gap-2.5 pt-1">
              <input
                id="lead-consent"
                type="checkbox"
                checked={marketingConsent}
                onChange={(e) => setMarketingConsent(e.target.checked)}
                disabled={isLoading}
                className="mt-1 h-4 w-4 rounded border-gray-300 text-brand-600 focus:ring-brand-500 cursor-pointer"
              />
              <label htmlFor="lead-consent" className="text-xs text-gray-600 leading-normal cursor-pointer select-none">
                Send me self-publishing tips, typography guides, and book formatting updates.
              </label>
            </div>

            {/* Privacy note */}
            <div className="flex items-center gap-1.5 text-xs text-gray-400 pt-1">
              <ShieldCheck className="h-4 w-4 text-gray-400" />
              <span>We never share your email or manuscript. Zero spam.</span>
            </div>

            {/* Actions */}
            <div className="mt-6 flex flex-col-reverse sm:flex-row gap-3 pt-2">
              <button
                type="button"
                onClick={onCancel}
                disabled={isLoading}
                className="btn-secondary w-full sm:w-auto text-sm justify-center py-2.5"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isLoading}
                className="btn-primary flex-1 text-sm justify-center py-2.5 shadow-md shadow-brand-500/20"
              >
                {isLoading ? (
                  <span className="flex items-center gap-2">
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                    Starting Demo…
                  </span>
                ) : (
                  'Start 15-Page Free Demo →'
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
