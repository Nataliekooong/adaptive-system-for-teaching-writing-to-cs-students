export type Role = "student" | "instructor";

export interface Me {
  id: number;
  username: string;
  display_name: string;
  role: Role;
}

export interface SettingSchema {
  key: string;
  type: "bool" | "int" | "float" | "enum" | "multi_enum" | "text";
  label: string;
  default: unknown;
  help: string;
  options: string[] | null;
  options_source: string | null;
  min: number | null;
  max: number | null;
}

export interface ModuleSchema {
  key: string;
  label: string;
  category: string;
  description: string;
  default_enabled: boolean;
  srs_refs: string[];
  settings: SettingSchema[];
  depends_on: string[];
}

export type ModuleValues = Record<string, unknown> & { enabled?: boolean };
/** Partial override: { module_key: { field: value } } */
export type ConfigOverrides = Record<string, ModuleValues>;
/** Fully resolved config. */
export type Config = Record<string, ModuleValues & { enabled: boolean }>;

export interface StyleRef {
  key: string;
  name: string;
  enabled: boolean;
}

export interface Registry {
  modules: ModuleSchema[];
  defaults: Config;
  styles: StyleRef[];
}

export interface Assignment {
  id: number;
  course_id: number;
  title: string;
  description: string;
  instructions: string;
  genre_guidance: string;
  due_date: string | null;
  rubric_areas: string[];
  get_started_content: string;
  published: boolean;
}

export interface FeedbackContentItem {
  rubric_area: string;
  comment: string;
  suggestion: string;
  quote: string;
}

export interface Feedback {
  id: number;
  venue: "on_demand" | "realtime";
  source: "slm" | "fixed_prompts";
  trigger: string | null;
  presentation: string;
  content: { summary: string; items: FeedbackContentItem[] };
  student_helpful: boolean | null;
  dismissed: boolean;
  created_at: string;
  // research fields (instructor only)
  style?: string | null;
  model_version?: string;
  prompt_template?: string;
  guardrail_status?: string;
  instructor_rating?: number | null;
  condition_id?: number | null;
}

export interface Course {
  id: number;
  code: string;
  title: string;
  rubric_areas: string[];
  config: ConfigOverrides;
  students?: number;
  assignments?: number;
  active_experiments?: number;
}

export interface Condition {
  id?: number;
  name: string;
  description: string;
  weight: number;
  config: ConfigOverrides;
  students?: number;
}

export interface Experiment {
  id: number;
  course_id: number;
  assignment_id: number | null;
  name: string;
  hypothesis: string;
  status: "draft" | "active" | "paused" | "completed";
  strategy: "random" | "balanced" | "manual";
  created_at: string;
  conditions: Condition[];
}

export interface UserRef {
  id: number;
  username: string;
  display_name: string;
  pseudonym: string;
}
