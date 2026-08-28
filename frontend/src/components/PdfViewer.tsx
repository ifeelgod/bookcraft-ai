'use client';

import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
import { Loader2, ChevronLeft, ChevronRight } from 'lucide-react';
import { useState } from 'react';

pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

interface PdfViewerProps {
  downloadUrl: string;
}

export default function PdfViewer({ downloadUrl }: PdfViewerProps) {
  const [numPages, setNumPages] = useState<number>(0);
  const [pageNumber, setPageNumber] = useState<number>(1);

  const onDocumentLoadSuccess = ({ numPages }: { numPages: number }) => {
    setNumPages(numPages);
  };

  const goPrev = () => {
    if (pageNumber === 1) return;
    if (pageNumber === 2) setPageNumber(1);
    else setPageNumber(Math.max(1, pageNumber - 2));
  };

  const goNext = () => {
    if (pageNumber === 1) setPageNumber(2);
    else setPageNumber(Math.min(numPages, pageNumber + 2));
  };

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-8 overflow-y-auto">
      <div className="flex items-center justify-center flex-1 w-full max-w-6xl relative">
        <Document
          file={downloadUrl}
          onLoadSuccess={onDocumentLoadSuccess}
          loading={<Loader2 className="h-8 w-8 animate-spin text-brand-600" />}
          className="flex gap-4 drop-shadow-2xl"
        >
          {pageNumber === 1 ? (
            <div className="flex w-full justify-center">
              <div className="w-1/2 flex justify-end">
                <Page pageNumber={1} renderAnnotationLayer={false} renderTextLayer={false} width={400} className="rounded-r-md overflow-hidden bg-white" />
              </div>
            </div>
          ) : (
            <div className="flex w-full justify-center gap-1">
              <div className="flex-1 flex justify-end">
                <Page pageNumber={pageNumber} renderAnnotationLayer={false} renderTextLayer={false} width={400} className="rounded-l-md overflow-hidden bg-white" />
              </div>
              <div className="flex-1 flex justify-start">
                {pageNumber + 1 <= numPages && (
                  <Page pageNumber={pageNumber + 1} renderAnnotationLayer={false} renderTextLayer={false} width={400} className="rounded-r-md overflow-hidden bg-white" />
                )}
              </div>
            </div>
          )}
        </Document>
      </div>
      <div className="mt-6 flex items-center gap-6 bg-white/90 backdrop-blur px-6 py-3 rounded-full shadow-lg border border-gray-200">
        <button
          onClick={goPrev}
          disabled={pageNumber <= 1}
          className="p-2 text-gray-600 hover:text-brand-600 hover:bg-brand-50 rounded-full disabled:opacity-30 transition-colors"
        >
          <ChevronLeft className="h-5 w-5" />
        </button>
        <span className="text-sm font-medium text-gray-700 min-w-[120px] text-center">
          {pageNumber === 1 ? 'Page 1' : `Pages ${pageNumber}-${Math.min(pageNumber + 1, numPages)}`} of {numPages}
        </span>
        <button
          onClick={goNext}
          disabled={pageNumber >= numPages}
          className="p-2 text-gray-600 hover:text-brand-600 hover:bg-brand-50 rounded-full disabled:opacity-30 transition-colors"
        >
          <ChevronRight className="h-5 w-5" />
        </button>
      </div>
    </div>
  );
}
