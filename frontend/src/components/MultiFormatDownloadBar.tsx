'use client';

import React, { useState } from 'react';
import { Download, FileText, Book, FileCode, Check, ChevronDown } from 'lucide-react';
import type { DownloadUrls } from '@/types/api';

interface MultiFormatDownloadBarProps {
  downloadUrls?: DownloadUrls | null;
  bookTitle?: string;
  className?: string;
}

export default function MultiFormatDownloadBar({
  downloadUrls,
  bookTitle = 'manuscript',
  className = '',
}: MultiFormatDownloadBarProps) {
  const [downloadedFormat, setDownloadedFormat] = useState<string | null>(null);

  if (!downloadUrls) return null;

  const safeTitle = (bookTitle || 'manuscript')
    .toLowerCase()
    .replace(/[^a-z0-9_-]/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_+|_+$/g, '') || 'manuscript';

  const handleDownloadClick = (formatKey: string) => {
    setDownloadedFormat(formatKey);
    setTimeout(() => setDownloadedFormat(null), 3000);
  };

  const formats = [
    {
      key: 'pdf',
      label: 'PDF',
      sublabel: 'Print-Ready & Interactive',
      ext: '.pdf',
      url: downloadUrls.pdf,
      icon: FileText,
      badgeColor: 'bg-red-50 text-red-700 border-red-200',
      btnClass: 'bg-red-600 hover:bg-red-700 text-white',
    },
    {
      key: 'docx',
      label: 'Word',
      sublabel: 'Editable .docx',
      ext: '.docx',
      url: downloadUrls.docx,
      icon: FileText,
      badgeColor: 'bg-blue-50 text-blue-700 border-blue-200',
      btnClass: 'bg-blue-600 hover:bg-blue-700 text-white',
    },
    {
      key: 'md',
      label: 'Markdown',
      sublabel: 'Clean .md',
      ext: '.md',
      url: downloadUrls.md,
      icon: FileCode,
      badgeColor: 'bg-purple-50 text-purple-700 border-purple-200',
      btnClass: 'bg-purple-600 hover:bg-purple-700 text-white',
    },
    {
      key: 'epub',
      label: 'EPUB',
      sublabel: 'E-reader ebook',
      ext: '.epub',
      url: downloadUrls.epub,
      icon: Book,
      badgeColor: 'bg-emerald-50 text-emerald-700 border-emerald-200',
      btnClass: 'bg-emerald-600 hover:bg-emerald-700 text-white',
    },
  ];

  const availableFormats = formats.filter((f) => !!f.url);
  if (availableFormats.length === 0) return null;

  return (
    <div className={`flex items-center flex-wrap gap-2 ${className}`}>
      {availableFormats.map((fmt) => {
        const Icon = fmt.icon;
        const isDownloaded = downloadedFormat === fmt.key;
        const downloadFileName = `${safeTitle}${fmt.ext}`;

        return (
          <a
            key={fmt.key}
            href={fmt.url}
            download={downloadFileName}
            onClick={() => handleDownloadClick(fmt.key)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg border border-gray-200 bg-white text-gray-700 hover:bg-gray-50 hover:border-gray-300 shadow-sm transition-all duration-150 group active:scale-95"
            title={`Download ${fmt.label} (${fmt.sublabel})`}
          >
            {isDownloaded ? (
              <Check className="h-3.5 w-3.5 text-green-600" />
            ) : (
              <Icon className="h-3.5 w-3.5 text-gray-500 group-hover:text-gray-700" />
            )}
            <span>{fmt.label}</span>
            <span className="text-[10px] text-gray-400 font-normal">{fmt.ext}</span>
            <Download className="h-3 w-3 text-gray-400 group-hover:text-brand-600 ml-0.5" />
          </a>
        );
      })}
    </div>
  );
}
