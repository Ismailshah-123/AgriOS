import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { jsonResponse, mockFetch, page, renderRoute, signedIn, testUser } from "../helpers";

/** Browser speech APIs are mocked: these tests cover AgriOS's behaviour, not recognition quality. */
class FakeRecognition {
  static last: FakeRecognition | null = null;
  lang = "";
  interimResults = true;
  continuous = true;
  onresult: ((e: unknown) => void) | null = null;
  onerror: ((e: { error: string }) => void) | null = null;
  onend: (() => void) | null = null;
  started = false;
  constructor() { FakeRecognition.last = this; }
  start() { this.started = true; }
  stop() { this.onend?.(); }
  say(text: string) {
    const result = Object.assign([{ transcript: text }], { isFinal: true });
    this.onresult?.({ results: [result] });
    this.onend?.();
  }
}

function urduUser() {
  const user = { ...testUser, locale: "ur" as const };
  return {
    ...signedIn,
    "POST /api/v1/auth/refresh": () => jsonResponse({ access_token: "tok", token_type: "bearer", expires_in: 900, user }),
    "GET /api/v1/auth/me": () => jsonResponse(user),
  };
}

const agentsData = {
  "GET /api/v1/fields": () => jsonResponse(page([])),
  "GET /api/v1/agent/runs": () => jsonResponse(page([])),
  "GET /api/v1/agent/actions": () => jsonResponse([]),
  "GET /api/v1/agent/catalogue": () => jsonResponse({ agents: [], tools: [], llm_used: false }),
};

afterEach(() => {
  vi.unstubAllGlobals();
  document.documentElement.dir = "ltr";
  FakeRecognition.last = null;
});

describe("Voice input", () => {
  it("puts recognised Urdu speech in the box for checking, without sending it", async () => {
    vi.stubGlobal("webkitSpeechRecognition", FakeRecognition);
    const fetchMock = mockFetch({ ...urduUser(), ...agentsData });
    const user = userEvent.setup();
    renderRoute("/agents");
    await user.click(await screen.findByRole("button", { name: "بولیں" }));
    expect(FakeRecognition.last!.lang).toBe("ur-PK");
    expect(FakeRecognition.last!.started).toBe(true);
    expect(screen.getByRole("status")).toHaveTextContent("ریکارڈنگ جاری ہے");
    act(() => FakeRecognition.last!.say("میرے ٹماٹر کے پتوں پر دھبے ہیں"));
    expect(screen.getByLabelText("Ask the agents")).toHaveValue("میرے ٹماٹر کے پتوں پر دھبے ہیں");
    expect(fetchMock.mock.calls.some(([u, i]) => String(u).includes("/agent/runs") && i?.method === "POST")).toBe(false);
  });

  it("explains a denied microphone in the user's language", async () => {
    vi.stubGlobal("webkitSpeechRecognition", FakeRecognition);
    mockFetch({ ...urduUser(), ...agentsData });
    const user = userEvent.setup();
    renderRoute("/agents");
    await user.click(await screen.findByRole("button", { name: "بولیں" }));
    act(() => FakeRecognition.last!.onerror?.({ error: "not-allowed" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("مائیکروفون کی اجازت نہیں ملی");
  });

  it("falls back to typing when the browser has no speech recognition", async () => {
    mockFetch({ ...signedIn, ...agentsData });
    renderRoute("/agents");
    expect(await screen.findByText(/Voice input is not available in this browser; please type/)).toBeInTheDocument();
    expect(screen.getByLabelText("Ask the agents")).toBeEnabled();
  });
});

describe("Voice output", () => {
  function stubSynthesis(voices: { lang: string; name: string }[]) {
    const spoken: { text: string; lang: string }[] = [];
    vi.stubGlobal("SpeechSynthesisUtterance", class { text: string; voice: unknown; lang = ""; onend: (() => void) | null = null; onerror: (() => void) | null = null; constructor(t: string) { this.text = t; } });
    vi.stubGlobal("speechSynthesis", {
      getVoices: () => voices,
      cancel: vi.fn(),
      speak: (u: { text: string; lang: string }) => spoken.push({ text: u.text, lang: u.lang }),
    });  // prettier-ignore
    return spoken;
  }
  const knowledge = {
    "GET /api/v1/knowledge/sources": () => jsonResponse([]),
    "GET /api/v1/knowledge/conversations": () => jsonResponse([]),
    "GET /api/v1/knowledge/taxonomy": () => jsonResponse({ domains: [], document_types: [], crops: [] }),
    "GET /api/v1/knowledge/stats": () => jsonResponse({ sources_by_status: {}, searchable_sources: 1, sources_with_chunks: 1, chunks: 1, embedded_chunks: 0,
      ingestion: {}, last_indexed_at: null, queries_total: 0, not_tracked: [],
      providers: { llm: { provider: "none", model: null, enabled: false, reason: null, external: false }, embeddings: { provider: "none", model: null, enabled: false } } }),
    "POST /api/v1/knowledge/ask": () => jsonResponse({ id: "q1", conversation_id: "c1", question: "x", retrieval_query: "x", language: "en", domain: null, crops: [],
      status: "extractive", answer: "> SYNTHETIC passage text. [S1]", citations: [], n_passages: 1, retrieval_ms: 1, total_ms: 1,
      meta: { warnings: [], evidence_quality: "single_passage", speech_text: "SYNTHETIC passage text." },
      llm_provider: null, llm_model: null, prompt_tokens: null, completion_tokens: null, feedback_rating: null, created_at: null }),
  };  // prettier-ignore

  async function searchAsUrduUser() {
    const user = userEvent.setup();
    mockFetch({ ...urduUser(), ...knowledge });
    renderRoute("/knowledge");
    // The knowledge page is localised for an Urdu profile: "Question" -> سوال, "Ask" -> پوچھیں.
    await user.type(await screen.findByLabelText("سوال"), "zorblat water");
    await user.click(screen.getByRole("button", { name: "پوچھیں" }));
    await screen.findByText("SYNTHETIC passage text.");
    return user;
  }

  it("reads a passage with an installed Urdu voice, then offers stop and repeat", async () => {
    const spoken = stubSynthesis([{ lang: "en-US", name: "en" }, { lang: "ur-PK", name: "ur" }]);
    const user = await searchAsUrduUser();
    await user.click(screen.getByRole("button", { name: "سنیں" }));
    expect(spoken).toEqual([{ text: "SYNTHETIC passage text.", lang: "ur-PK" }]);
    expect(screen.getByRole("button", { name: "روکیں" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "روکیں" }));
    expect(screen.getByRole("button", { name: "دوبارہ سنیں" })).toBeInTheDocument();
  });

  it("refuses to read Urdu with an English voice and says why", async () => {
    const spoken = stubSynthesis([{ lang: "en-US", name: "en" }]);
    const user = await searchAsUrduUser();
    await user.click(screen.getByRole("button", { name: "سنیں" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("اردو آواز موجود نہیں"));
    expect(spoken).toEqual([]);
  });
});
