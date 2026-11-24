import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { AskResult, KnowledgeStats } from "@/services/api/knowledge";
import { callsTo, expectNoA11yViolations, jsonResponse, mockFetch, renderRoute, signedIn, testUser } from "../helpers";

// SYNTHETIC fixtures (invented crop "zorblat"): not agricultural knowledge.
const stats = (searchable: number): KnowledgeStats => ({
  sources_by_status: { unverified: 0, licence_verified: searchable, content_reviewed: 0, blocked: 0 },
  searchable_sources: searchable, sources_with_chunks: searchable, chunks: searchable * 2, embedded_chunks: searchable * 2,
  ingestion: { not_ingested: 0, queued: 0, processing: 0, indexed: searchable, failed: 0 }, last_indexed_at: null, queries_total: 0,
  providers: { llm: { provider: "none", model: null, enabled: false, reason: null, external: false },
    embeddings: { provider: "none", model: null, enabled: false } },
  not_tracked: ["embedding cost"],
});  // prettier-ignore

const answer = (over: Partial<AskResult> = {}): AskResult => ({
  id: "q1", conversation_id: "c1", question: "zorblat spots", retrieval_query: "zorblat spots", language: "en", domain: null, crops: [],
  status: "answered", answer: "Grey spots on zorblat come from a synthetic fungus [S1].\n\n- Keep foliage dry [S1].",
  citations: [{ n: 1, marker: "S1", cited: true, chunk_id: "k1", text: "SYNTHETIC passage about zorblat spots.", page: 7, section: "Leaf spots",
    source_id: "s1", title: "Synthetic doc", publisher: "Test", author: null, year: 2026, publication_date: null, url: null,
    licence: "test-only", review_status: "licence_verified", document_type: null, fts_rank: 0.3, dense_score: 0.71, matched_by: ["full_text", "dense"] }],
  meta: { warnings: ["invalid_citation_removed"], evidence_quality: "single_passage", speech_text: "SYNTHETIC passage text.",
    retrieval_method: "hybrid", farm_context: null },
  n_passages: 1, retrieval_ms: 40, total_ms: 900, llm_provider: "fake", llm_model: "m", prompt_tokens: 10, completion_tokens: 5,
  feedback_rating: null, created_at: null, ...over,
});  // prettier-ignore

const base = (searchable: number) => ({
  ...signedIn,
  "GET /api/v1/knowledge/stats": () => jsonResponse(stats(searchable)),
  "GET /api/v1/knowledge/sources": () => jsonResponse([]),
  "GET /api/v1/knowledge/conversations": () => jsonResponse([]),
  "GET /api/v1/knowledge/taxonomy": () => jsonResponse({ domains: ["plant_protection"], document_types: ["factsheet"], crops: ["tomato"] }),
});

describe("Agricultural Knowledge (FR8 RAG)", () => {
  it("abstains honestly, then shows a cited answer with warnings, sources and the passage viewer", async () => {
    let n = 0;
    const fetch = mockFetch({
      ...base(1),
      "POST /api/v1/knowledge/ask": () => jsonResponse(n++ === 0
        ? answer({ status: "abstained", answer: "No verified guidance found. Ask an expert.", citations: [], meta: { warnings: [], evidence_quality: "none", speech_text: "" } })
        : answer()),
      "GET /api/v1/knowledge/chunks/k1": () => jsonResponse({ chunk: { id: "k1", page: 7, section: "Leaf spots", text: "SYNTHETIC passage about zorblat spots." },
        context: [{ id: "k1", page: 7, section: "Leaf spots", text: "SYNTHETIC passage about zorblat spots.", is_cited: true }],
        source: { id: "s1", title: "Synthetic doc", url: null, attribution: "Test attribution", has_file: false } }),
    });  // prettier-ignore
    const user = userEvent.setup();
    const { container } = renderRoute("/knowledge");
    await user.type(await screen.findByLabelText("Question"), "wheat rust");
    await user.click(screen.getByRole("button", { name: "Ask" }));
    expect(await screen.findByText("No verified guidance found. Ask an expert.")).toBeInTheDocument();
    await expectNoA11yViolations(container);
    await user.type(screen.getByLabelText("Follow-up question"), "zorblat spots");
    await user.click(screen.getByRole("button", { name: "Ask" }));
    expect(await screen.findByText("Grounded answer")).toBeInTheDocument();
    expect(screen.getByText("AI-written from cited sources")).toBeInTheDocument();
    expect(screen.getByText(/did not match a retrieved passage was removed/)).toBeInTheDocument();
    const sources = screen.getByRole("region", { name: "Sources" });
    expect(within(sources).getByText("Synthetic doc")).toBeInTheDocument();
    expect(within(sources).getByText(/p\. 7 · Leaf spots · licence: test-only/)).toBeInTheDocument();
    expect(callsTo(fetch, "POST", "/api/v1/knowledge/ask")[1]!.body).toMatchObject({ question: "zorblat spots", conversation_id: "c1" });
    await user.click(within(sources).getByRole("button", { name: "Open source" }));
    expect(await screen.findByText("Cited passage · p. 7 · Leaf spots")).toBeInTheDocument();
    expect(screen.getByText("Attribution: Test attribution")).toBeInTheDocument();
  });

  it("says the library is empty and hides admin controls and analytics from farmers", async () => {
    mockFetch(base(0));
    const user = userEvent.setup();
    renderRoute("/knowledge");
    expect(await screen.findByText(/verified source library is empty/)).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Analytics" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Sources" }));
    expect(await screen.findByRole("heading", { name: "No sources registered" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Register source" })).not.toBeInTheDocument();
  });

  it("gives administrators source registration and measured analytics", async () => {
    const admin = { ...testUser, role: "admin" as const };
    mockFetch({
      ...base(1),
      "POST /api/v1/auth/refresh": () => jsonResponse({ access_token: "tok", token_type: "bearer", expires_in: 900, user: admin }),
      "GET /api/v1/auth/me": () => jsonResponse(admin),
      "GET /api/v1/knowledge/analytics": () => jsonResponse({ queries_total: 3, by_status: { answered: 2, abstained: 1 }, no_result_queries: 1, failed_queries: 0,
        by_domain: { plant_protection: 3 }, by_language: { en: 2, ur: 1 }, latency_ms: { retrieval_p50: 50, retrieval_p95: 70, total_p50: 900, total_p95: 2000 },
        tokens: { prompt: 100, completion: 50 }, daily: [{ day: "2026-11-24", queries: 3 }], source_usage: [{ title: "Synthetic doc", citations: 4 }],
        feedback: { helpful: 1, not_helpful: 0 }, ingestion: { indexed: 1 }, ingestion_jobs: { succeeded: 1 }, not_tracked: ["answer accuracy"] }),
    });  // prettier-ignore
    const user = userEvent.setup();
    renderRoute("/knowledge");
    await user.click(await screen.findByRole("tab", { name: "Analytics" }));
    expect(await screen.findByText("50 ms")).toBeInTheDocument();
    expect(screen.getByLabelText("Question languages")).toHaveTextContent("Urdu");
    await user.click(screen.getByRole("tab", { name: "Sources" }));
    expect(await screen.findByRole("button", { name: "Register source" })).toBeInTheDocument();
  });
});
