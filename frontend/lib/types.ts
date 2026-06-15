export interface UploadResponse {
  session_id: string;
  status: string;
  message: string;
}

export interface ProgressStep {
  name: string;
  status: "pending" | "active" | "completed" | "error";
}

export interface ProgressResponse {
  session_id: string;
  status: string;
  current_step: string | null;
  steps: ProgressStep[];
  uploaded_file_name?: string | null;
}

export interface ProjectInfo {
  project_name: string | null;
  site_address: string | null;
  city: string | null;
  state: string | null;
  zip_code: string | null;
  detected_file_type: string | null;
  detected_relevant_pages: Record<string, unknown> | null;
}

export interface WindowItem {
  id: string;
  tag: string | null;
  material_type: string;
  width: string | null;
  height: string | null;
  area: string | null;
  quantity: string | null;
  opening_type: string | null;
  material: string | null;
  u_value: string | null;
  shgc: string | null;
  vt: string | null;
  glass_type: string | null;
  confidence: number;
  notes: string | null;
}

export interface DoorItem {
  id: string;
  tag: string | null;
  material_type: string;
  width: string | null;
  height: string | null;
  area: string | null;
  quantity: string | null;
  opening_type: string | null;
  material: string | null;
  fire_rating: string | null;
  self_closing: string | null;
  glass_type: string | null;
  confidence: number;
  notes: string | null;
}

export interface ExtractionResponse {
  session_id: string;
  project_info: ProjectInfo | null;
  window_items: WindowItem[];
  // Optional for backward-compat with older backends; defaults to [] in the UI.
  door_items?: DoorItem[];
  warnings: string[];
}

export interface PatchExtractionRequest {
  project_info?: Partial<Omit<ProjectInfo, "detected_file_type" | "detected_relevant_pages">>;
  window_items?: Array<Partial<WindowItem> & { id: string }>;
  door_items?: Array<Partial<DoorItem> & { id: string }>;
}

export interface ConfirmResponse {
  session_id: string;
  status: string;
  next: string;
}

export interface QuoteRow {
  tag: string;
  supplier: string;
  unit_price: number;
  quantity: number;
  estimated_total: number;
  lead_time_days: number;
  match_score: number;
  match_reason: string;
  risk_notes: string;
}

export interface RecommendationsResponse {
  session_id: string;
  quote_table: QuoteRow[];
  natural_language_summary: string;
}
