/**
 * TypeScript types mirroring the DocumentAST JSON schema
 * and API response shapes.
 */

// ────────────────────────────────────────────────────────────
// Content Blocks
// ────────────────────────────────────────────────────────────

export type BlockType =
  | 'paragraph'
  | 'heading2'
  | 'heading3'
  | 'callout'
  | 'pullquote'
  | 'table'
  | 'interactive-field'
  | 'image'
  | 'page-break'
  | 'horizontal-rule';

export interface ParagraphBlock {
  id?: string;
  type: 'paragraph';
  text: string;
  indent?: boolean;
  align?: 'left' | 'center' | 'right' | 'justify';
}

export interface Heading2Block {
  id?: string;
  type: 'heading2';
  text: string;
  numbering?: boolean;
}

export interface Heading3Block {
  id?: string;
  type: 'heading3';
  text: string;
}

export interface CalloutBlock {
  id?: string;
  type: 'callout';
  variant?: 'info' | 'tip' | 'warning' | 'danger' | 'success';
  title?: string;
  text: string;
}

export interface PullquoteBlock {
  id?: string;
  type: 'pullquote';
  text: string;
  attribution?: string;
  align?: 'left' | 'center' | 'right';
}

export interface TableBlock {
  id?: string;
  type: 'table';
  caption?: string;
  headers: string[];
  rows: string[][];
  column_alignments?: ('left' | 'center' | 'right')[];
  striped?: boolean;
}

export interface InteractiveFieldBlock {
  id?: string;
  type: 'interactive-field';
  field_type: 'text' | 'multiline' | 'checkbox' | 'radio' | 'date' | 'signature';
  label: string;
  placeholder?: string;
  required?: boolean;
  options?: string[];
  lines?: number;
}

export interface ImageBlock {
  id?: string;
  type: 'image';
  src: string;
  alt?: string;
  caption?: string;
  width?: string;
  align?: 'left' | 'center' | 'right';
}

export interface PageBreakBlock {
  id?: string;
  type: 'page-break';
}

export interface HorizontalRuleBlock {
  id?: string;
  type: 'horizontal-rule';
  style?: 'line' | 'dots' | 'asterisks' | 'ornament';
}

export type ContentBlock =
  | ParagraphBlock
  | Heading2Block
  | Heading3Block
  | CalloutBlock
  | PullquoteBlock
  | TableBlock
  | InteractiveFieldBlock
  | ImageBlock
  | PageBreakBlock
  | HorizontalRuleBlock;

// ────────────────────────────────────────────────────────────
// Chapter
// ────────────────────────────────────────────────────────────

export interface Epigraph {
  text: string;
  attribution?: string;
}

export interface Chapter {
  id?: string;
  chapter_number: number;
  title: string;
  subtitle?: string;
  epigraph?: Epigraph;
  content: ContentBlock[];
  word_count?: number;
  notes?: string;
}

// ────────────────────────────────────────────────────────────
// Front Matter
// ────────────────────────────────────────────────────────────

export interface TitlePage {
  enabled?: boolean;
  display_title?: string;
  display_subtitle?: string;
  display_author?: string;
  display_publisher?: string;
}

export interface CopyrightPage {
  enabled?: boolean;
  year?: number;
  holder?: string;
  statement?: string;
  rights_reserved?: boolean;
  printed_in?: string;
  edition?: string;
  disclaimer?: string;
}

export interface TableOfContents {
  enabled?: boolean;
  title?: string;
  include_subheadings?: boolean;
  max_depth?: 1 | 2 | 3;
}

export interface DedicationPage {
  enabled?: boolean;
  text?: string;
}

export interface FrontMatter {
  title_page?: TitlePage;
  copyright?: CopyrightPage;
  table_of_contents?: TableOfContents;
  dedication?: DedicationPage;
}

// ────────────────────────────────────────────────────────────
// Metadata & Settings
// ────────────────────────────────────────────────────────────

export type Genre =
  | 'fiction' | 'non-fiction' | 'biography' | 'self-help'
  | 'business' | 'academic' | 'children' | 'poetry'
  | 'anthology' | 'technical' | 'other';

export type TrimSize = '5.5x8.5' | '6x9' | '8.5x11';

export interface BookMetadata {
  title: string;
  subtitle?: string;
  author: string;
  co_authors?: string[];
  genre: Genre;
  trim_size: TrimSize;
  isbn?: string;
  publisher?: string;
  published_year?: number;
  edition?: string;
  language?: string;
  keywords?: string[];
  cover_image_url?: string;
}

export interface CompilationSettings {
  font_family?: 'Garamond' | 'Times New Roman' | 'Georgia' | 'Palatino' | 'Helvetica' | 'Arial';
  font_size?: number;
  line_height?: number;
  margins?: { top: number; bottom: number; inner: number; outer: number };
}

// ────────────────────────────────────────────────────────────
// Root DocumentAST
// ────────────────────────────────────────────────────────────

export interface DocumentAST {
  metadata: BookMetadata;
  front_matter: FrontMatter;
  chapters: Chapter[];
  compilation_settings: CompilationSettings;
}

// ────────────────────────────────────────────────────────────
// API Response Types
// ────────────────────────────────────────────────────────────

export interface UploadResponse {
  job_id: string;
  status: string;
  message: string;
  file_name: string;
  size_bytes: number;
}

export interface CompileResponse {
  job_id: string;
  status: string;
  message: string;
  book_title: string;
}

export interface JobStatus {
  job_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number;
  message: string;
  file_name?: string;
  created_at: string;
  updated_at: string;
  result?: Record<string, unknown>;
  error?: string;
  download_url?: string;
}
