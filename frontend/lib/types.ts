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

export interface ExtractionResponse {
  session_id: string;
  project_info: ProjectInfo | null;
  window_items: WindowItem[];
  warnings: string[];
}

export interface PatchExtractionRequest {
  project_info?: Partial<Omit<ProjectInfo, "detected_file_type" | "detected_relevant_pages">>;
  window_items?: Array<Partial<WindowItem> & { id: string }>;
}
