'use client';

import { BookOpen, Settings, Download, ArrowLeft, Loader2, ChevronLeft, ChevronRight, FileText, Upload, Sparkles, Crown, Lock } from 'lucide-react';
import Link from 'next/link';
import { useState, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import toast from 'react-hot-toast';
import { compileDocument, pollJobStatus, getAst } from '@/lib/api';
import { useAuth } from '@/lib/authStore';
import { CheckoutModal } from '@/components/CheckoutModal';
import type { DocumentAST, JobStatus, DownloadUrls } from '@/types/api';
import MultiFormatDownloadBar from '@/components/MultiFormatDownloadBar';

import dynamic from 'next/dynamic';

const PdfViewer = dynamic(() => import('@/components/PdfViewer'), { ssr: false });

const SAMPLE_AST: DocumentAST = {
  metadata: {
    title: 'My Book',
    author: 'Jane Doe',
    genre: 'non-fiction',
    trim_size: '6x9',
  },
  front_matter: {
    title_page: { enabled: true },
    copyright: { enabled: true, year: new Date().getFullYear(), holder: 'Jane Doe' },
    table_of_contents: { enabled: true },
    dedication: { enabled: false },
  },
  chapters: [
    {
      chapter_number: 1,
      title: 'Introduction',
      content: [
        { type: 'paragraph', text: 'Welcome to my book. This is the opening paragraph.' },
        { type: 'heading2', text: 'Why This Book?' },
        { type: 'paragraph', text: 'This book was written because...' },
        {
          type: 'callout',
          variant: 'tip',
          title: 'Pro Tip',
          text: 'Read each chapter carefully before moving on.',
        },
      ],
    },
  ],
  compilation_settings: {
    font_family: 'Garamond',
    font_size: 11,
    line_height: 1.5,
    margins: { top: 0.7, bottom: 0.7, inner: 0.75, outer: 0.5 },
  },
};

type CompileState = 'idle' | 'compiling' | 'done' | 'error';

const PRESETS: Record<string, { font_family: any; font_size: number; line_height: number }> = {
  'Literary Classic': { font_family: 'Garamond', font_size: 11, line_height: 1.5 },
  'Modern Business': { font_family: 'Helvetica', font_size: 11, line_height: 1.6 },
  'Minimalist': { font_family: 'Arial', font_size: 10, line_height: 1.8 },
  'Action Workbook': { font_family: 'Arial', font_size: 12, line_height: 1.4 },
};

function EditorContent() {
  const searchParams = useSearchParams();
  const initialJobId = searchParams.get('jobId');
  const { isPro, tier, token } = useAuth();

  const [ast, setAst] = useState<DocumentAST | null>(null);
  const [preset, setPreset] = useState<string>('Literary Classic');
  const [modalOpen, setModalOpen] = useState<boolean>(false);

  const [loadingAst, setLoadingAst] = useState<boolean>(true);
  const [compileState, setCompileState] = useState<CompileState>('idle');
  const [progress, setProgress] = useState(0);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [downloadUrls, setDownloadUrls] = useState<DownloadUrls | null>(null);
  const [errorMsg, setErrorMsg] = useState('');

  useEffect(() => {
    if (!initialJobId) {
      setAst(SAMPLE_AST);
      setLoadingAst(false);
      return;
    }

    const fetchAst = async () => {
      try {
        const result = await getAst(initialJobId);
        setAst(result.ast);
        toast.success('Loaded uploaded document successfully!');
      } catch (err) {
        console.error(err);
        toast.error('Failed to load document AST, falling back to sample.');
        setAst(SAMPLE_AST);
      } finally {
        setLoadingAst(false);
      }
    };

    fetchAst();
  }, [initialJobId]);

  const handleCompile = async (astToCompile: DocumentAST = ast!) => {
    if (!astToCompile) return;
    
    setCompileState('compiling');
    setProgress(0);
    setErrorMsg('');

    try {
      const res = await compileDocument(astToCompile, token || undefined, isPro ? 'pro' : 'demo');
      await pollJobStatus(res.job_id, (status: JobStatus) => {
        setProgress(status.progress);
        if (status.status === 'completed') {
          setCompileState('done');
          const pdfUrl = (status.download_urls?.pdf ?? status.result?.download_urls?.pdf ?? status.download_url ?? status.result?.download_url) as string ?? null;
          const urls = (status.download_urls ?? status.result?.download_urls ?? (pdfUrl ? { pdf: pdfUrl } : null)) as DownloadUrls | null;
          setDownloadUrl(pdfUrl);
          setDownloadUrls(urls);
        } else if (status.status === 'failed') {
          setCompileState('error');
          setErrorMsg(status.error ?? 'Unknown error');
        }
      });
    } catch (err: unknown) {
      setCompileState('error');
      setErrorMsg(err instanceof Error ? err.message : 'Compilation failed');
    }
  };

  const handleUpdateAst = (updates: Partial<DocumentAST>) => {
    if (!ast) return;
    const newAst = { ...ast, ...updates };
    setAst(newAst);
    handleCompile(newAst); // Auto-compile on change
  };

  const chapters = ast?.chapters || [];

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header Bar */}
      <div className="border-b border-gray-200 bg-white px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/" className="text-gray-400 hover:text-gray-700">
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <BookOpen className="h-6 w-6 text-brand-600" />
          <span className="text-xl font-bold text-gray-900 tracking-tight">BookCraft AI</span>
          {isPro ? (
            <div className="flex items-center gap-1.5 px-2.5 py-1 bg-amber-500/10 border border-amber-500/30 rounded-full text-amber-600 text-xs font-semibold">
              <Crown className="w-3.5 h-3.5 text-amber-500" />
              <span>{tier?.toUpperCase()} TIER</span>
            </div>
          ) : (
            <div className="flex items-center gap-1.5 px-2.5 py-1 bg-slate-100 border border-slate-200 rounded-full text-slate-600 text-xs">
              <span>Demo (15-Page Limit)</span>
            </div>
          )}
        </div>
        <div className="flex items-center gap-3">
          {!isPro && (
            <button
              onClick={() => setModalOpen(true)}
              className="px-3 py-1.5 text-xs font-bold text-white bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 rounded-lg shadow-sm flex items-center gap-1.5 transition-all"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Upgrade to Pro ($19)</span>
            </button>
          )}
          <Link href="/upload" className="btn-secondary text-sm flex items-center gap-2">
            <Upload className="h-4 w-4" /> Upload New File
          </Link>
          {compileState === 'done' && (
            <div className="flex items-center gap-2">
              <MultiFormatDownloadBar downloadUrls={downloadUrls} bookTitle={ast?.metadata?.title} />
              {downloadUrl && (
                <a href={downloadUrl} className="btn-primary text-sm flex items-center gap-2" download={`${ast?.metadata?.title || 'book'}.pdf`}>
                  <Download className="h-4 w-4" /> View PDF
                </a>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Checkout Upgrade Modal */}
      <CheckoutModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        onSuccess={() => {
          toast.success('Pro Tier activated! Compiling full manuscript...');
          if (ast) handleCompile(ast);
        }}
      />

      {/* Progress bar */}
      {compileState === 'compiling' && (
        <div className="h-1 w-full bg-gray-200">
          <div className="h-1 bg-brand-600 transition-all duration-500" style={{ width: `${progress}%` }} />
        </div>
      )}

      {/* Main layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left Pane (Controls & Structure) */}
        <div className="w-1/3 min-w-[320px] max-w-sm bg-white border-r border-gray-200 flex flex-col overflow-y-auto p-6 space-y-8">
          
          {loadingAst ? (
            <div className="flex items-center gap-2 text-gray-500">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading document...
            </div>
          ) : (
            <>
              {/* Settings Section */}
              <section>
                <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wider mb-4">Book Settings</h3>
                <div className="space-y-4">
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">Typography Preset</label>
                    <select
                      className="block w-full rounded-md border-gray-300 shadow-sm focus:border-brand-500 focus:ring-brand-500 sm:text-sm bg-gray-50 p-2 border"
                      value={preset}
                      onChange={(e) => {
                        const newPreset = e.target.value;
                        setPreset(newPreset);
                        handleUpdateAst({
                          compilation_settings: {
                            ...ast!.compilation_settings,
                            ...PRESETS[newPreset]
                          } as any
                        });
                      }}
                    >
                      {Object.keys(PRESETS).map(p => (
                        <option key={p} value={p}>{p}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">Trim Size</label>
                    <select
                      className="block w-full rounded-md border-gray-300 shadow-sm focus:border-brand-500 focus:ring-brand-500 sm:text-sm bg-gray-50 p-2 border"
                      value={ast?.metadata?.trim_size || '6x9'}
                      onChange={(e) => {
                        handleUpdateAst({
                          metadata: { ...ast!.metadata, trim_size: e.target.value as any }
                        });
                      }}
                    >
                      <option value="5.5x8.5">5.5" x 8.5" (Trade Paperback)</option>
                      <option value="6x9">6" x 9" (US Trade)</option>
                      <option value="8.5x11">8.5" x 11" (Workbook / Letter)</option>
                    </select>
                  </div>
                </div>
              </section>

              {/* Chapter Tree Section */}
              <section className="flex-1">
                <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wider mb-4">Table of Contents</h3>
                <div className="space-y-2">
                  {chapters.map((chapter, idx) => (
                    <div key={idx} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg border border-gray-100 hover:border-gray-200 transition-colors">
                      <FileText className="h-4 w-4 text-gray-400 flex-shrink-0" />
                      <div className="min-w-0 flex-1">
                        <input
                          type="text"
                          className="w-full bg-transparent text-sm font-medium text-gray-900 focus:outline-none focus:ring-1 focus:ring-brand-500 rounded px-1"
                          value={chapter.title}
                          onChange={(e) => {
                            const newChapters = [...chapters];
                            newChapters[idx].title = e.target.value;
                            setAst({ ...ast!, chapters: newChapters });
                          }}
                          onBlur={() => handleCompile(ast!)}
                        />
                        <p className="text-xs text-gray-500 px-1 truncate">{chapter.content.length} blocks</p>
                      </div>
                    </div>
                  ))}
                  {chapters.length === 0 && (
                    <p className="text-sm text-gray-500 italic">No chapters found.</p>
                  )}
                </div>
              </section>
            </>
          )}

        </div>

        {/* Right Pane (Live Book Preview) */}
        <div className="flex-1 bg-gray-200 flex flex-col relative overflow-hidden">
          {compileState === 'idle' && !downloadUrl && !loadingAst && (
            <div className="absolute inset-0 flex items-center justify-center">
              <button onClick={() => handleCompile()} className="btn-primary">
                Generate Live Preview
              </button>
            </div>
          )}

          {compileState === 'error' && (
            <div className="absolute inset-0 flex items-center justify-center p-8">
              <div className="bg-white p-6 rounded-xl shadow-lg border border-red-100 max-w-lg w-full text-center">
                <h3 className="text-lg font-bold text-red-700 mb-2">Compilation Error</h3>
                <p className="text-sm text-gray-600 mb-4">{errorMsg}</p>
                <button onClick={() => handleCompile()} className="btn-secondary">Try Again</button>
              </div>
            </div>
          )}

          {downloadUrl && <PdfViewer downloadUrl={downloadUrl} />}
        </div>
      </div>
    </div>
  );
}

export default function EditorPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center"><Loader2 className="h-8 w-8 animate-spin" /></div>}>
      <EditorContent />
    </Suspense>
  );
}
