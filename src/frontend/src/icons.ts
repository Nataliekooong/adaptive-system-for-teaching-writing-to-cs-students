/** App-owned icons live here so pages never choose their own glyphs. */
export const icons = {
  writing: "✍️", instructor: "🧑‍🏫", student: "🧑‍🎓", developer: "🧑‍💻",
  home: "🏠", course: "🎓", assignment: "📝", document: "📄", submissions: "📨",
  complete: "✅", experiments: "🧪", modules: "🧩", review: "⭐", students: "👥",
  library: "📚", research: "📊", feedback: "💬", realtime: "⚡", presentation: "🎭",
  helpful: "👍", unhelpful: "👎", target: "🎯", learner: "🧠", questionnaire: "📋",
  getStarted: "🚀", history: "🕘", rules: "📏", styles: "🎨", prompts: "📌",
  bandit: "🎰", welcome: "👋", character: "🦉", highlight: "🖍️", date: "📅",
  visible: "👁", search: "🔍", template: "✨", warning: "⚠️", saved: "☁",
  menu: "☰", collapse: "«", logout: "↩︎", expand: "▶", add: "＋", check: "✓",
  close: "✕", download: "⬇", back: "←", forward: "→", undo: "↶", redo: "↷",
  pause: "Ⅱ", stop: "■", number: "#", text: "Aa", bullet: "●",
  timer: "⏱️", receipt: "🧾", log: "📜", paused: "⏸", random: "🎲", idea: "💡",
  created: "🕐", delete: "🗑", hidden: "🙈", identity: "🆔", anonymous: "🕶",
  struggle: "🔥", edit: "✎", celebrate: "🎉", guide: "🧭", error: "❌", status: "◉",
} as const;

const MODULE_ICONS: Record<string, string> = {
  on_demand_feedback: icons.feedback, realtime_feedback: icons.realtime,
  feedback_presentation: icons.presentation, student_rating: icons.helpful,
  instructor_review: icons.instructor, reward: icons.target, learner_model: icons.learner,
  questionnaire: icons.questionnaire, get_started: icons.getStarted, version_history: icons.history,
  paste_control: icons.questionnaire, submission_rules: icons.rules, grades: icons.course,
};

export function moduleIcon(key: string): string {
  return MODULE_ICONS[key] ?? icons.modules;
}

export const assignmentStatusIcons = {
  in_progress: icons.assignment, submitted: icons.submissions, graded: icons.complete,
};
