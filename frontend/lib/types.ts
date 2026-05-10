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
