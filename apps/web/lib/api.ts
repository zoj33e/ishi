import type { components } from "./api-types";

type Schemas = components["schemas"];
export type Health = Schemas["Health"];
export type GameState = Schemas["GameStateOut"];
export type SandboxState = Schemas["SandboxState"];
export type ApiErrorDetail = Schemas["ErrorDetail"];

/** A failed call: the backend's error body, or a synthetic one when the server is unreachable. */
export class ApiError extends Error {
  constructor(readonly detail: ApiErrorDetail) {
    super(detail.code);
  }
}

/** All requests go to the same origin; Next.js rewrites /api/* to FastAPI. */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      cache: "no-store",
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError({ code: "NETWORK", message_key: "errors.network", details: {} });
  }
  const body: unknown = await res.json().catch(() => null);
  if (!res.ok) {
    const err = (body as Schemas["ErrorResponse"] | null)?.error;
    throw new ApiError(err ?? { code: `HTTP_${res.status}`, message_key: "errors.invalid_request", details: {} });
  }
  return body as T;
}

export function fetchHealth(): Promise<Health> {
  return request<Health>("/api/health");
}

export function fetchSandboxState(body: Schemas["SandboxRequest"]): Promise<SandboxState> {
  return request<SandboxState>("/api/sandbox/state", { method: "POST", body: JSON.stringify(body) });
}

// -- M2: profile, school, capture games, exam ------------------------------------------------

export type Me = Schemas["MeOut"];
export type Today = Schemas["TodayOut"];
export type School = Schemas["SchoolOut"];
export type LessonDetail = Schemas["LessonOut"];
export type LessonTask = Schemas["TaskOut"];
export type Position = Schemas["Position"];
export type AnswerIn = Schemas["AnswerIn"];
export type AnswerOut = Schemas["AnswerOut"];
export type MoveOut = Schemas["MoveOut"];
export type Exam = Schemas["ExamOut"];
export type Locale = "th" | "en";

const json = (body: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body) });

export const getMe = () => request<Me>("/api/me");
export const patchMe = (body: Schemas["MePatch"]) =>
  request<Me>("/api/me", { method: "PATCH", body: JSON.stringify(body) });
export const getToday = () => request<Today>("/api/today");

export const getSchool = (locale: Locale) => request<School>(`/api/school?locale=${locale}`);
export const getLesson = (id: string, locale: Locale) =>
  request<LessonDetail>(`/api/school/${encodeURIComponent(id)}?locale=${locale}`);
export const answerTask = (lessonId: string, taskId: string, body: AnswerIn) =>
  request<AnswerOut>(
    `/api/school/${encodeURIComponent(lessonId)}/tasks/${encodeURIComponent(taskId)}/answer`,
    json(body),
  );

export type NewGame = Schemas["NewGame"];
export type BotRanks = Schemas["BotRanksOut"];

export const createGame = (body: NewGame) => request<GameState>("/api/games", json(body));
export const getBotRanks = () => request<BotRanks>("/api/games/bot-ranks");
export const getGame = (id: string) => request<GameState>(`/api/games/${encodeURIComponent(id)}`);
export const playMove = (id: string, point: string) =>
  request<MoveOut>(`/api/games/${encodeURIComponent(id)}/moves`, json({ point }));
export const resignGame = (id: string) =>
  request<GameState>(`/api/games/${encodeURIComponent(id)}/resign`, { method: "POST" });

export const startExam = () => request<Exam>("/api/exams", { method: "POST" });
export const getExam = (id: string) => request<Exam>(`/api/exams/${encodeURIComponent(id)}`);

// -- M5: post-game lessons -------------------------------------------------------------------

export type GameLesson = Schemas["GameLessonOut"];
export type Narration = Schemas["Narration"];
export type RetryOut = Schemas["RetryOut"];
export type LessonStatus = Schemas["GameLessonPreparing"]["status"];

/** The game's lesson, or its status while the teacher is still preparing it (HTTP 202). */
export async function getGameLesson(
  gameId: string,
  locale: Locale,
): Promise<{ lesson: GameLesson } | { status: LessonStatus }> {
  const body = await request<GameLesson | Schemas["GameLessonPreparing"]>(
    `/api/games/${encodeURIComponent(gameId)}/lesson?locale=${locale}`,
  );
  return "lesson_id" in body ? { lesson: body } : { status: body.status };
}
export const retryLesson = (id: string, point: string) =>
  request<RetryOut>(`/api/lessons/${encodeURIComponent(id)}/retry`, json({ point }));
export const lessonHint = (id: string) =>
  request<GameLesson>(`/api/lessons/${encodeURIComponent(id)}/hint`, { method: "POST" });
export const finishLesson = (id: string) =>
  request<Schemas["DoneOut"]>(`/api/lessons/${encodeURIComponent(id)}/done`, { method: "POST" });

// -- M6: Shape Gym ---------------------------------------------------------------------------

export type GymPuzzle = Schemas["PuzzleOut"];
export type GymDue = Schemas["DueOut"];
export type GymAttempt = Schemas["AttemptOut"];
export type GymHint = Schemas["HintOut"];
export type GymContext = Schemas["AttemptIn"]["context"];

export const getGymDue = (context: GymContext) => request<GymDue>(`/api/gym/due?context=${context}`);
export const gymAttempt = (id: string, body: Schemas["AttemptIn"]) =>
  request<GymAttempt>(`/api/gym/puzzles/${encodeURIComponent(id)}/attempt`, json(body));
export const gymHint = (id: string, body: Schemas["HintIn"]) =>
  request<GymHint>(`/api/gym/puzzles/${encodeURIComponent(id)}/hint`, json(body));
