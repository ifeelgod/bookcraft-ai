import Link from 'next/link';
import {
  BookOpen,
  Upload,
  Wand2,
  FileText,
  ArrowRight,
  Sparkles,
} from 'lucide-react';

const features = [
  {
    icon: Upload,
    title: 'Upload Your Manuscript',
    description:
      'Import .docx or PDF files. BookCraft AI parses your document and builds a structured AST automatically.',
  },
  {
    icon: Wand2,
    title: 'AI-Powered Formatting',
    description:
      'Powered by DeepSeek via OpenRouter, our AI intelligently structures content blocks, chapters, and front matter.',
  },
  {
    icon: FileText,
    title: 'Compile to PDF',
    description:
      'Output publication-ready PDFs in standard trim sizes: 5.5×8.5, 6×9, and 8.5×11 inches.',
  },
];

export default function HomePage() {
  return (
    <div className="min-h-screen">
      {/* ── Nav ── */}
      <nav className="border-b border-gray-200 bg-white/80 backdrop-blur sticky top-0 z-50">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 items-center justify-between">
            <div className="flex items-center gap-2">
              <BookOpen className="h-7 w-7 text-brand-600" />
              <span className="text-xl font-bold text-gray-900">BookCraft AI</span>
            </div>
            <div className="flex items-center gap-3">
              <Link href="/upload" className="btn-secondary text-xs py-2 px-3">
                Upload File
              </Link>
              <Link href="/editor" className="btn-primary text-xs py-2 px-3">
                Open Editor
              </Link>
            </div>
          </div>
        </div>
      </nav>

      {/* ── Hero ── */}
      <section className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8 pt-20 pb-16 text-center">
        <div className="inline-flex items-center gap-2 rounded-full bg-brand-50 px-4 py-1.5 text-sm font-medium text-brand-700 ring-1 ring-brand-200 mb-6">
          <Sparkles className="h-4 w-4" />
          Powered by DeepSeek via OpenRouter
        </div>

        <h1 className="text-5xl font-bold tracking-tight text-gray-900 sm:text-6xl">
          From manuscript to
          <br />
          <span className="text-brand-600">publication-ready</span>
          <br />
          in minutes.
        </h1>

        <p className="mt-6 text-lg leading-8 text-gray-600 max-w-2xl mx-auto">
          BookCraft AI transforms your Word documents and PDFs into beautifully
          formatted books. Upload, structure, and compile — all in one platform.
        </p>

        <div className="mt-10 flex items-center justify-center gap-4">
          <Link href="/upload" className="btn-primary px-6 py-3 text-base">
            Get Started <ArrowRight className="h-4 w-4" />
          </Link>
          <Link href="/editor" className="btn-secondary px-6 py-3 text-base">
            Open Editor
          </Link>
        </div>
      </section>

      {/* ── Features ── */}
      <section className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8 pb-24">
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
          {features.map((f) => (
            <div key={f.title} className="card hover:shadow-md transition-shadow">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-brand-50 ring-1 ring-brand-200 mb-4">
                <f.icon className="h-6 w-6 text-brand-600" />
              </div>
              <h3 className="text-base font-semibold text-gray-900 mb-2">{f.title}</h3>
              <p className="text-sm text-gray-600 leading-relaxed">{f.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="border-t border-gray-200 py-8 text-center text-sm text-gray-500">
        <p>BookCraft AI © {new Date().getFullYear()} — Built with Next.js 14 &amp; FastAPI</p>
      </footer>
    </div>
  );
}
