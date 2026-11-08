export type Stage =
  | "k0"
  | "tutorial"
  | "t1_ready"
  | "t1_active"
  | "k1"
  | "k2"
  | "t2_ready"
  | "t2_active"
  | "k3"
  | "survey"
  | "peer_assessment"
  | "social_feed"
  | "complete";

export type AssessmentKind = "k0" | "k1" | "k2" | "k3" | "survey";

export interface PhaseInfo {
  id: string;
  label_zh: string;
  label_en: string;
}

export interface Guide {
  version: string;
  phase: string;
  hint_used: boolean;
  completed_at: string | null;
  phases: PhaseInfo[];
}

export interface StudentState {
  participant: {
    id: string;
    class_id: number;
    class_name: string;
  };
  run_id: string;
  stage: Stage;
  stage_label: string;
  step: number;
  total_steps: number;
  completed: boolean;
  assessment_kind: AssessmentKind | null;
  assessment_label: string | null;
  active_round: {
    round_no: number;
    task: "T1" | "T2";
    started_at: string;
    deadline_at: string;
    remaining_seconds: number;
    artifact_title: string;
    guide: Guide | null;
    image_job_limit?: number;
  } | null;
  server_time: string;
}

export interface ArtifactSection {
  key: string;
  title: string;
  body: string;
  /** Optional English reading aid; never used for scoring. */
  title_en?: string;
  body_en?: string;
  source_ids: string[];
  media_keys: string[];
}

export interface ArtifactMedia {
  key: string;
  caption: string;
  alt: string;
  url: string;
  original_url: string;
  mime: string;
  width?: number;
  height?: number;
}

export interface Artifact {
  id: string;
  title: string;
  title_en?: string;
  introduction_en?: string;
  era: string;
  type: string;
  object_code?: string | null;
  introduction: string;
  facts: string[];
  evidence: string[];
  uncertainty: string[];
  sections?: ArtifactSection[];
  media?: ArtifactMedia[];
  rights_status?: string;
  image_url: string;
}

export interface ImageJob {
  id: string;
  status: "queued" | "running" | "succeeded" | "failed";
  prompt: string;
  attempts: number;
  error_code: string | null;
  error_message: string | null;
  image_url: string | null;
  width: number | null;
  height: number | null;
  created_at: string;
  finished_at: string | null;
}

export interface StructuredFields {
  cultural_features: string;
  historical_function: string;
  sources_evidence: string;
  cultural_continuity: string;
  cultural_translation: string;
  innovation_rationale: string;
}

export interface RationaleFields {
  heritage_knowledge: string;
  cultural_translation: string;
  design_reason: string;
}

export interface Work {
  product_name: string;
  product_category: string;
  target_audience: string;
  design_concept: string;
  structured_fields: StructuredFields;
  rationale_fields: RationaleFields;
  open_statement: string;
  image_prompt: string;
  revision: number;
  updated_at: string | null;
}

export interface RoundData {
  round_no: number;
  task: "T1" | "T2";
  task_label: string;
  work_form: "structured" | "open" | "rationale";
  artifact: Artifact;
  work: Work;
  started_at: string;
  deadline_at: string;
  remaining_seconds: number;
  finished: boolean;
  image_jobs: ImageJob[];
  selected_image_job_id?: string | null;
  image_job_limit: number;
  guide: Guide | null;
}

export interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  source: string;
  content: string;
  created_at: string;
}

export interface Option {
  value: string;
  label: string;
  /** Optional English reading aid; the answer value is unchanged. */
  label_en?: string;
  allow_text?: boolean;
}

export interface QuestionRow {
  id: string;
  label: string;
}

export interface Question {
  id: string;
  type:
    | "single_choice"
    | "multi_choice"
    | "short_text"
    | "evidence_judgment"
    | "likert";
  prompt: string;
  /** Optional English reading aid; the Chinese prompt remains the instrument text. */
  prompt_en?: string | null;
  section?: string | null;
  required: boolean;
  options?: Option[];
  max_length?: number;
  rows?: QuestionRow[];
  scale_min?: number;
  scale_max?: number;
  scale_labels?: string[];
}

export interface Instrument {
  id: string;
  kind: AssessmentKind;
  version: number;
  title: string;
  title_en?: string | null;
  instructions: string;
  instructions_en?: string | null;
  questions: Question[];
}

export interface AssessmentPayload {
  instrument: Instrument;
  answers: Record<string, unknown>;
  status: "draft" | "submitted";
  started_at: string | null;
  updated_at: string | null;
  artifact_image_url?: string | null;
  server_time?: string;
}

export interface ReadinessCheck {
  key: string;
  label: string;
  ok: boolean;
  detail: string;
}

export interface Readiness {
  deployment_mode?: "beta" | "study";
  ready_to_activate: boolean;
  ready_for_students: boolean;
  checks: ReadinessCheck[];
  active_protocol: ProtocolSummary | null;
  latest: {
    artifacts: Record<string, ArtifactSummary>;
    instruments: Record<string, InstrumentSummary>;
  };
  participant_count: number;
  run_count: number;
  demo_present: boolean;
}

export interface ArtifactSummary {
  id: string;
  slot: string;
  version: number;
  title: string;
  era: string;
  type: string;
  has_image: boolean;
  is_demo: boolean;
  created_at: string;
  image_url: string | null;
}

export interface InstrumentSummary {
  id: string;
  kind: string;
  version: number;
  title: string;
  object_code?: string | null;
  form_code?: string | null;
  is_demo: boolean;
  created_at: string;
}

export interface ProtocolSummary {
  id: string;
  artifact_x_version_id: string;
  artifact_y_version_id: string;
  instrument_versions: Record<string, string>;
  assessment_version?: string | null;
  is_demo: boolean;
  activated_at: string | null;
}

export interface AdminArtifact extends Artifact {
  slot: string;
  object_code?: string | null;
  version: number;
  is_demo: boolean;
  rights_status?: string;
  content_sha256?: string | null;
  created_at: string;
  image_sha256: string | null;
}

export interface AdminInstrument extends Instrument {
  object_code?: string | null;
  form_code?: string | null;
  is_demo: boolean;
}

export interface PeerDimension {
  key: string;
  short?: string;
  label: string;
  prompt: string;
  anchors?: string[];
}

export interface PeerReviewScale {
  version: string;
  title: string;
  instructions: string;
  principles: string[];
  comment_prompt: string;
  score_min: number;
  score_max: number;
  dimensions: PeerDimension[];
}

export interface PeerAssignment {
  assignment_id: string;
  work_code: string;
  round_no?: 1 | 2;
  artifact_title?: string | null;
  artifact_era?: string;
  artifact_type?: string;
  artifact_introduction?: string;
  image_available?: boolean;
  product_name: string;
  product_category: string;
  design_concept: string;
  rationale_fields?: RationaleFields;
  structured_fields?: Record<string, string>;
  open_statement: string;
  image_url: string | null;
  status: "pending" | "submitted";
  scores: Record<string, number>;
  comment: string;
}

export interface PeerGate {
  status: "collecting" | "open";
  entered: number;
  t2_ended: number;
  valid_work_count: number;
  t1_work_count?: number;
  t2_work_count?: number;
  can_open: boolean;
  message: string;
}

export interface PeerPayload {
  deployment_mode?: "beta" | "study";
  waiting?: boolean;
  gate?: PeerGate;
  batch: {
    id: string;
    algorithm_version: string;
    scale_version?: string;
    review_version?: string;
    eligible_work_count: number;
    work_target?: number | null;
    reviewer_target?: number | null;
  } | null;
  review?: PeerReviewScale | null;
  assignments: PeerAssignment[];
  completed: boolean;
  submitted: number;
  total: number;
}

export interface ClassPeerGate {
  deployment_mode?: "beta" | "study";
  continuous_entry?: boolean;
  class_id: number;
  class_name: string;
  status: "collecting" | "open";
  entered: number;
  t2_ended: number;
  valid_work_count: number;
  t1_work_count?: number;
  t2_work_count?: number;
  can_open: boolean;
  membership_frozen_at: string | null;
  peer_opened_at: string | null;
  entered_count_at_open: number;
  t2_ended_count_at_open: number;
  valid_work_count_at_open: number;
  batch_id: string | null;
  last_event: {
    event_type: string;
    counts: Record<string, number>;
    created_at: string;
  } | null;
}

export interface ClassEntryLink {
  id: string;
  class_id: number;
  label: string;
  active: boolean;
  url: string | null;
  created_at: string;
  revoked_at: string | null;
}

export interface PortfolioWork {
  round_no: number;
  artifact_title: string;
  image_url: string | null;
  product_name: string;
  product_category: string;
  target_audience: string;
  design_concept: string;
  statement: string;
}

export interface SocialWork {
  work_id: number;
  work_code: string;
  product_name: string;
  product_category: string;
  design_concept: string;
  rationale_fields?: RationaleFields;
  open_statement: string;
  image_url: string | null;
  is_own: boolean;
  liked_by_me: boolean;
}
