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
  is_demo?: boolean;
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
// Lead & API Response Types
// ────────────────────────────────────────────────────────────

export interface LeadFormData {
  name: string;
  email: string;
  marketingConsent: boolean;
  tier?: string;
}

export interface DownloadUrls {
  pdf?: string;
  docx?: string;
  md?: string;
  epub?: string;
  [key: string]: string | undefined;
}

export interface UploadResponse {
  job_id: string;
  lead_id?: string;
  tier?: string;
  status: string;
  is_truncated?: boolean;
  preflight_message?: string;
  message: string;
  file_name: string;
  size_bytes: number;
}

export interface CompileResponse {
  job_id: string;
  status: string;
  message: string;
  book_title: string;
  download_urls?: DownloadUrls;
}

export interface JobStatus {
  job_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number;
  message: string;
  file_name?: string;
  created_at: string;
  updated_at: string;
  result?: {
    output_path?: string;
    download_url?: string;
    download_urls?: DownloadUrls;
    formats?: Record<string, { path: string; url: string; size_bytes: number }>;
    ast?: DocumentAST;
    [key: string]: unknown;
  };
  error?: string;
  download_url?: string;
  download_urls?: DownloadUrls;
}

// ────────────────────────────────────────────────────────────
// Payment & Auth Types
// ────────────────────────────────────────────────────────────

export interface PricingTierFeature {
  text: string;
  included: boolean;
}

export interface PricingTierInfo {
  id: string;
  name: string;
  price_cents: number;
  price_display: string;
  period: string;
  popular?: boolean;
  features: string[];
}

export interface PaymentConfigResponse {
  mode: string;
  stripe: {
    enabled: boolean;
    publishable_key: string;
    price_pro_pass: string;
    price_author_pro: string;
  };
  paypal: {
    enabled: boolean;
    client_id: string;
    environment: string;
    price_pro_pass: string;
    price_author_pro: string;
  };
  tiers: PricingTierInfo[];
}

export interface CheckoutRequestPayload {
  provider: 'stripe' | 'paypal';
  tier: string;
  lead_email?: string;
  lead_name?: string;
  success_url?: string;
  cancel_url?: string;
  metadata?: Record<string, any>;
}

export interface CheckoutResult {
  provider: string;
  session_id: string;
  checkout_url: string;
  amount_cents: number;
  currency: string;
  tier: string;
  mode?: string;
}

export interface VerifyPaymentPayload {
  provider: 'stripe' | 'paypal';
  session_id?: string;
  order_id?: string;
  lead_email?: string;
  lead_name?: string;
  tier?: string;
}

export interface VerifyPaymentResult {
  success: boolean;
  status: string;
  access_token: string;
  tier: string;
  email?: string;
  lead_id?: string;
  payment_id?: string;
  transaction_id?: string;
  amount_cents?: number;
  currency?: string;
  expires_at?: string;
}

export interface AuthStateData {
  token: string | null;
  tier: 'demo' | 'pro' | 'pro_pass' | 'author_pro' | 'tier_1_pass' | 'tier_2_monthly' | 'tier_3_monthly' | 'tier_3_annual';
  email: string | null;
  name: string | null;
  expiresAt: string | null;
}

