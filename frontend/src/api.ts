const API_BASE = "http://localhost:8000";

export interface StartInterviewResponse {
  session_id: string;
  question: string;
  question_key: string;
}

export interface AnswerResponse {
  status: "in_progress" | "awaiting_menu_choice" | "completed";
  question?: string;
  question_key?: string;
  menu?: string[];
  result?: boolean;
  feedback_output?: string;
}

export async function startInterview(
  jobDescription: string,
  userId: string
): Promise<StartInterviewResponse> {
  const res = await fetch(`${API_BASE}/interview/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_description: jobDescription, user_id: userId }),
  });
  if (!res.ok) throw new Error("Failed to start interview");
  return res.json();
}

export async function submitAnswer(
  sessionId: string,
  answer: string
): Promise<AnswerResponse> {
  const res = await fetch(`${API_BASE}/interview/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, answer }),
  });
  if (!res.ok) throw new Error("Failed to submit answer");
  return res.json();
}

export async function fetchSpeechAudioUrl(text: string): Promise<string> {
  const res = await fetch(`${API_BASE}/interview/speak`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) throw new Error("Failed to fetch speech audio");
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}
