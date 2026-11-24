import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { EMPTY_OBSERVATIONS } from "@/features/crop-health/observations";
import { _resetMemoryDrafts, saveDraft } from "@/features/offline/drafts";
import type { CaseDetail, CaseListItem } from "@/services/api/cropHealth";
import {
  callsTo,
  expectNoA11yViolations,
  jsonResponse,
  mockFetch,
  mockXhr,
  page,
  photoFile,
  renderRoute,
  signedIn,
  testUser,
} from "../helpers";

const farm = { id: "f-1", name: "Green Acres" };
const field = { id: "fd-1", farm_id: "f-1", farm_name: "Green Acres", name: "North Field" };
const cycle = {
  id: "cy-1", field_id: "fd-1", field_name: "North Field", farm_id: "f-1", farm_name: "Green Acres",
  crop: { id: "c-tom", code: "tomato", name_en: "Tomato" }, variety: null, status: "active",
  sowing_date: "2026-10-01",
};  // prettier-ignore

const item: CaseListItem = {
  id: "case-1", reference: "CD-000001", status: "submitted", inference_status: "model_unavailable",
  crop: { id: "c-tom", code: "tomato", name: "Tomato" }, farm: { id: "f-1", name: "Green Acres" },
  field: { id: "fd-1", name: "North Field" }, crop_cycle_id: "cy-1", image_count: 1,
  submission_count: 1, thumb_url: "/api/v1/files/case-images/i1/thumb?exp=1&sig=x",
  created_at: "2026-11-23T08:00:00Z", last_activity_at: "2026-11-23T08:00:00Z",
};  // prettier-ignore

const img = { id: "i1", position: 0, width: 400, height: 300, url: "/full", thumb_url: "/thumb", urls_expire_at: "2026-11-23T08:10:00Z" };

function detail(over: Partial<CaseDetail> = {}): CaseDetail {
  return {
    ...item, consent_training: false,
    submissions: [{ id: "s1", kind: "initial", plant_part: "leaf", symptoms: ["spots"], observed_on: "2026-11-20",
      notes: "Brown spots", submitted_at: "2026-11-23T08:00:00Z", images: [img] }],
    analysis: { inference_status: "model_unavailable", model_availability: "not_registered", error_code: null,
      message: "No validated analysis model is installed yet. Your photos are saved and can be analysed once a model is available.",
      can_retry: true, result: null },
    timeline: [{ at: "2026-11-23T08:00:00Z", kind: "created", text: "Case submitted" }],
    ...over,
  };  // prettier-ignore
}

const summary = { total: 4, awaiting_analysis: 3, needs_follow_up: 1, by_inference_status: {}, model_availability: "not_registered" };

describe("Crop Doctor overview", () => {
  it("shows real counts, recent cases and the honest model status", async () => {
    mockFetch({
      ...signedIn,
      "GET /api/v1/cases/summary": () => jsonResponse(summary),
      "GET /api/v1/cases": () => jsonResponse(page([item])),
    });
    renderRoute("/crop-doctor");
    const tiles = await screen.findByRole("region", { name: "Case summary" });
    expect(within(tiles).getByText("4")).toBeInTheDocument();
    expect(within(tiles).getByText("3")).toBeInTheDocument();
    expect(screen.getByText("No model installed")).toBeInTheDocument();
    expect(screen.getByText(/No diagnosis is shown until then/)).toBeInTheDocument();
    const recent = await screen.findByRole("list", { name: "Recent cases" });
    expect(within(recent).getByRole("link", { name: /CD-000001/ })).toHaveAttribute("href", "/crop-doctor/cases/case-1");
  });
});

describe("New assessment", () => {
  const data = {
    ...signedIn,
    "GET /api/v1/farms": () => jsonResponse(page([farm])),
    "GET /api/v1/fields": () => jsonResponse(page([field])),
    "GET /api/v1/crop-cycles": () => jsonResponse(page([cycle])),
  };

  it("cascades farm, field and growing crop, validates, and uploads with progress", async () => {
    const fetchMock = mockFetch({ ...data, "GET /api/v1/cases/case-1": () => jsonResponse(detail()) });
    const xhr = mockXhr(() => ({ status: 201, body: detail() }));
    const user = userEvent.setup();
    const { router } = renderRoute("/crop-doctor/new");
    await user.click(await screen.findByRole("button", { name: "Submit assessment" }));
    expect(await screen.findByText("Choose a farm.")).toBeInTheDocument();
    expect(screen.getByText("Add at least one photo.")).toBeInTheDocument();
    expect(xhr).toHaveLength(0);

    const fieldSelect = screen.getByLabelText("Field");
    expect(fieldSelect).toBeDisabled();
    await user.selectOptions(screen.getByLabelText("Farm"), "f-1");
    await user.selectOptions(fieldSelect, "fd-1");
    await user.selectOptions(screen.getByLabelText("Growing crop"), "cy-1");

    await user.upload(screen.getByLabelText("Choose photos"), [photoFile("a.jpg"), photoFile("b.png", "image/png")]);
    expect(await screen.findByRole("list", { name: "Selected photos" })).toBeInTheDocument();
    expect(screen.getAllByRole("img", { name: /Selected photo/ })).toHaveLength(2);
    await user.click(screen.getByRole("button", { name: "Remove photo 2" }));
    expect(screen.getAllByRole("img", { name: /Selected photo/ })).toHaveLength(1);

    await user.click(screen.getByText("Spots"));
    await user.type(screen.getByLabelText(/Notes/), "Brown spots on lower leaves");
    await user.click(screen.getByRole("button", { name: "Submit assessment" }));

    await waitFor(() => expect(router.state.location.pathname).toBe("/crop-doctor/cases/case-1"));
    expect(xhr).toHaveLength(1);
    const form = xhr[0]!.form;
    expect(xhr[0]!.url).toBe("/api/v1/cases");
    expect(form.get("crop_cycle_id")).toBe("cy-1");
    expect(form.getAll("symptoms")).toEqual(["spots"]);
    expect(form.get("notes")).toBe("Brown spots on lower leaves");
    expect(form.get("consent_training")).toBe("false");
    expect(form.getAll("images")).toHaveLength(1);
    const fieldCalls = callsTo(fetchMock, "GET", "/api/v1/fields");
    expect(fieldCalls.some((c) => c.url.searchParams.get("farm_id") === "f-1")).toBe(true);
    expect(form.get("client_id")).toMatch(/^[0-9a-f-]{36}$/); // idempotency key on every upload
  });

  it("keeps a case on the device when the connection drops, then uploads it once with the same client_id", async () => {
    _resetMemoryDrafts();
    mockFetch({ ...data, "GET /api/v1/cases/summary": () => jsonResponse(summary), "GET /api/v1/cases": () => jsonResponse(page([])) });
    let online = false;
    const xhr = mockXhr(() => (online ? { status: 201, body: detail() } : { status: 0, body: null }));
    const user = userEvent.setup();
    const { router } = renderRoute("/crop-doctor/new");
    await user.selectOptions(await screen.findByLabelText("Farm"), "f-1");
    await user.selectOptions(screen.getByLabelText("Field"), "fd-1");
    await user.selectOptions(screen.getByLabelText("Growing crop"), "cy-1");
    await user.upload(screen.getByLabelText("Choose photos"), [photoFile("a.jpg")]);
    await user.click(screen.getByRole("button", { name: "Submit assessment" }));

    // Stays on the form (other route code may be unloadable offline) and confirms the save.
    expect(await screen.findByText(/Saved on this device. It will upload automatically/)).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/crop-doctor/new");
    expect(await screen.findByRole("heading", { name: "Saved on this device" })).toBeInTheDocument();
    expect(screen.getByText("Not uploaded yet")).toBeInTheDocument();
    expect(screen.getByText(/Kept only until this browser tab closes/)).toBeInTheDocument(); // jsdom: no IndexedDB

    online = true;
    await user.click(screen.getByRole("button", { name: "Upload now" }));
    expect(await screen.findByText("1 case uploaded.")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Saved on this device" })).not.toBeInTheDocument();
    expect(xhr).toHaveLength(2);
    expect(xhr[1]!.form.get("client_id")).toBe(xhr[0]!.form.get("client_id")); // server de-duplicates on this
    expect(xhr[1]!.form.getAll("images")).toHaveLength(1);
  });

  it("marks a draft the server refuses as needing attention instead of retrying forever", async () => {
    _resetMemoryDrafts();
    await saveDraft({
      client_id: "11111111-2222-3333-4444-555555555555", user_id: testUser.id, created_at: "2026-11-24T00:00:00Z",
      status: "pending", last_error: null, input: { crop_cycle_id: "cy-gone", consent_training: false, ...EMPTY_OBSERVATIONS },
      photos: [{ name: "a.jpg", type: "image/jpeg", blob: photoFile("a.jpg") }],
    });  // prettier-ignore
    mockFetch({ ...data, "GET /api/v1/cases/summary": () => jsonResponse(summary), "GET /api/v1/cases": () => jsonResponse(page([])) });
    mockXhr(() => ({ status: 404, body: { error: { code: "not_found", message: "Crop cycle not found.", field: "crop_cycle_id" } } }));
    const user = userEvent.setup();
    renderRoute("/crop-doctor");
    await user.click(await screen.findByRole("button", { name: "Upload now" }));
    expect(await screen.findByText("Needs attention")).toBeInTheDocument();
    expect(screen.getByText("Crop cycle not found.")).toBeInTheDocument();
    _resetMemoryDrafts();
  });

  it("rejects unsupported files and too many photos before uploading", async () => {
    mockFetch(data);
    const user = userEvent.setup({ applyAccept: false });
    renderRoute("/crop-doctor/new");
    const input = await screen.findByLabelText("Choose photos");
    await user.upload(input, [photoFile("notes.txt", "text/plain"), photoFile("x.gif", "image/gif")]);
    expect(await screen.findByText("notes.txt: use a JPEG, PNG or WebP photo.")).toBeInTheDocument();
    await user.upload(input, Array.from({ length: 6 }, (_, i) => photoFile(`p${i}.jpg`)));
    expect(await screen.findByText("You can add up to 5 photos.")).toBeInTheDocument();
    expect(screen.getAllByRole("img", { name: /Selected photo/ })).toHaveLength(5);
    expect(screen.getByRole("button", { name: "Choose photos" })).toBeDisabled();
  });

  it("shows server-side photo rejections next to the photos", async () => {
    mockFetch(data);
    mockXhr(() => ({ status: 422, body: { error: { code: "image_unreadable", message: "Photo 1: This file could not be read as a photo.", field: "images" } } }));
    const user = userEvent.setup();
    renderRoute("/crop-doctor/new");
    await user.selectOptions(await screen.findByLabelText("Farm"), "f-1");
    await user.selectOptions(screen.getByLabelText("Field"), "fd-1");
    await user.selectOptions(screen.getByLabelText("Growing crop"), "cy-1");
    await user.upload(screen.getByLabelText("Choose photos"), [photoFile()]);
    await user.click(screen.getByRole("button", { name: "Submit assessment" }));
    expect(await screen.findByText("Photo 1: This file could not be read as a photo.")).toBeInTheDocument();
  });

  it("explains that a growing crop is needed first", async () => {
    mockFetch({ ...signedIn, "GET /api/v1/farms": () => jsonResponse(page([])), "GET /api/v1/fields": () => jsonResponse(page([])),
      "GET /api/v1/crop-cycles": () => jsonResponse(page([])) });  // prettier-ignore
    renderRoute("/crop-doctor/new");
    expect(await screen.findByRole("heading", { name: "No growing crops yet" })).toBeInTheDocument();
  });
});

describe("Case details", () => {
  it("shows photos, farmer observations and model-unavailable status without any diagnosis", async () => {
    const fetchMock = mockFetch({
      ...signedIn,
      "GET /api/v1/cases/case-1": () => jsonResponse(detail()),
      "POST /api/v1/cases/case-1/analysis/retry": () => jsonResponse({ ...detail().analysis, inference_status: "queued", can_retry: false }),
    });
    const user = userEvent.setup();
    const { container } = renderRoute("/crop-doctor/cases/case-1");
    expect(await screen.findByRole("heading", { level: 1, name: "Case CD-000001" })).toBeInTheDocument();
    expect(screen.getByText("Farmer observations")).toBeInTheDocument();
    expect(screen.getByText("Brown spots")).toBeInTheDocument();
    expect(screen.getByText(/No validated analysis model is installed yet/)).toBeInTheDocument();
    expect(screen.queryByText(/Most likely|confidence/i)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Open photo 1 full size" }));
    expect(await screen.findByRole("img", { name: "Case photo 1" })).toHaveAttribute("src", "/full");
    await user.keyboard("{Escape}");
    await user.click(screen.getByRole("button", { name: "Request analysis again" }));
    await waitFor(() => expect(callsTo(fetchMock, "POST", "/api/v1/cases/case-1/analysis/retry")).toHaveLength(1));
    await expectNoA11yViolations(container);
  });

  it("shows a result only after completed inference, and never a class when unsure", async () => {
    const result = { decision: "unsure" as const, predicted_class: null, calibrated_confidence: 0.41, ood_score: -3.2,
      shortlist: [{ label: "Early blight", probability: 0.41 }, { label: "Healthy", probability: 0.33 }],
      model_name: "tomato-mnv3", model_version: "1.0.0", analysed_at: "2026-11-23T09:00:00Z", image_count: 1,
      explanation_available: false, limits_note: "Decision support only." };  // prettier-ignore
    mockFetch({ ...signedIn, "GET /api/v1/cases/case-1": () => jsonResponse(detail({
      inference_status: "completed", status: "unsure",
      analysis: { inference_status: "completed", model_availability: "ready", error_code: null, message: "Analysis complete.", can_retry: false, result },
    })) });  // prettier-ignore
    renderRoute("/crop-doctor/cases/case-1");
    expect(await screen.findByText(/The model is not sure. No diagnosis is given/)).toBeInTheDocument();
    expect(screen.queryByText("Most likely")).not.toBeInTheDocument();
    expect(screen.getByText("Possibilities considered (this photo)")).toBeInTheDocument();
    expect(screen.getByText(/Decision support only\. Model tomato-mnv3 1\.0\.0/)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /Where the model looked/ })).not.toBeInTheDocument();
    expect(screen.getByText(/No heatmap for this result: this model version does not provide/)).toBeInTheDocument();
  });

  it("shows no class possibilities and no heatmap note for an out-of-scope photo", async () => {
    const result = { decision: "out_of_scope" as const, predicted_class: null, calibrated_confidence: 0.9, ood_score: -3.1,
      shortlist: [{ label: "late_blight", probability: 0.9 }, { label: "early_blight", probability: 0.06 }],
      model_name: "crop_doctor_tomato", model_version: "1.0.0", analysed_at: "2026-11-25T04:26:00Z", image_count: 1,
      explanation_available: false, limits_note: "Decision support only." };  // prettier-ignore
    mockFetch({ ...signedIn, "GET /api/v1/cases/case-1": () => jsonResponse(detail({
      inference_status: "completed", status: "out_of_scope",
      analysis: { inference_status: "completed", model_availability: "ready", error_code: null, message: "Analysis complete.", can_retry: false, result },
    })) });  // prettier-ignore
    renderRoute("/crop-doctor/cases/case-1");
    expect(await screen.findByText(/does not look like the tomato leaves the model was trained on/)).toBeInTheDocument();
    expect(screen.queryByText("Possibilities considered (this photo)")).not.toBeInTheDocument();
    expect(screen.queryByText(/Late blight/)).not.toBeInTheDocument();
    expect(screen.queryByText(/No heatmap for this result/)).not.toBeInTheDocument();
  });

  it("overlays the class activation map inside the model's crop box, with legend and limits", async () => {
    const result = { decision: "accepted" as const, predicted_class: "Early blight", calibrated_confidence: 0.93, ood_score: -8,
      shortlist: [{ label: "Early blight", probability: 0.93 }], model_name: "tomato-effb0", model_version: "1.0.0",
      analysed_at: "2026-11-23T09:00:00Z", image_count: 1, explanation_available: true, limits_note: "Decision support only." };
    const explanation = { available: true, reason: null, method: "class_activation_map", target_class: "Early blight",
      decision: "accepted", note: "An explanation aid, not proof of the cause.", model_name: "tomato-effb0", model_version: "1.0.0",
      limits_note: "Decision support only.", maps: [{ image: img, grid: [[0, 0.5], [1, 0.25]], crop_box: [0.2083, 0.0625, 0.5833, 0.875] }] };
    mockFetch({ ...signedIn,
      "GET /api/v1/cases/case-1": () => jsonResponse(detail({ inference_status: "completed", status: "accepted",
        analysis: { inference_status: "completed", model_availability: "ready", error_code: null, message: "Analysis complete.", can_retry: false, result } })),
      "GET /api/v1/cases/case-1/explanation": () => jsonResponse(explanation),
    });  // prettier-ignore
    const { container } = renderRoute("/crop-doctor/cases/case-1");
    expect(await screen.findByRole("heading", { name: "Where the model looked: Early blight" })).toBeInTheDocument();
    const box = screen.getByRole("img", { name: "Analysed photo 1" }).nextElementSibling as HTMLElement;
    expect(box.style.left).toBe("20.83%");
    expect(box.style.width).toBe("58.33%");
    expect(box.children).toHaveLength(4); // 2 x 2 grid cells
    expect(screen.getByLabelText("Heatmap legend")).toHaveTextContent("regions that raised the score");
    expect(screen.getByText(/not proof of the cause/)).toBeInTheDocument();
    await expectNoA11yViolations(container);
  });

  it("adds a follow-up observation and keeps earlier history", async () => {
    mockFetch({ ...signedIn, "GET /api/v1/cases/case-1": () => jsonResponse(detail()) });
    const xhr = mockXhr(() => ({ status: 201, body: detail() }));
    const user = userEvent.setup();
    renderRoute("/crop-doctor/cases/case-1");
    await user.click(await screen.findByRole("button", { name: "Add follow-up" }));
    const dialog = await screen.findByRole("dialog", { name: "Add a follow-up" });
    await user.click(within(dialog).getByRole("button", { name: "Add follow-up" }));
    expect(await within(dialog).findByText("Add a photo or an observation.")).toBeInTheDocument();
    await user.type(within(dialog).getByLabelText(/Notes/), "Spreading to upper leaves");
    await user.click(within(dialog).getByRole("button", { name: "Add follow-up" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(xhr[0]!.url).toBe("/api/v1/cases/case-1/follow-ups");
    expect(xhr[0]!.form.get("notes")).toBe("Spreading to upper leaves");
  });

  it("shows not-found for another user's case", async () => {
    mockFetch({ ...signedIn, "GET /api/v1/cases/x": () => jsonResponse({ error: { code: "not_found", message: "Case not found." } }, 404) });
    renderRoute("/crop-doctor/cases/x");
    expect(await screen.findByRole("heading", { name: "Case not found" })).toBeInTheDocument();
  });
});

describe("Case history", () => {
  it("filters through the API and loads more pages", async () => {
    const fetchMock = mockFetch({
      ...signedIn,
      "GET /api/v1/crops": () => jsonResponse([{ id: "c-tom", code: "tomato", name_en: "Tomato" }]),
      "GET /api/v1/cases": ({ url }) =>
        url.searchParams.get("cursor")
          ? jsonResponse(page([{ ...item, id: "case-2", reference: "CD-000002" }]))
          : jsonResponse({ items: [item], next_cursor: "next" }),
    });
    const user = userEvent.setup();
    renderRoute("/crop-doctor/cases");
    expect(await screen.findByText("CD-000001")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Load more cases" }));
    expect(await screen.findByText("CD-000002")).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Analysis status"), "model_unavailable");
    await user.selectOptions(screen.getByLabelText("Crop"), "c-tom");
    await waitFor(() =>
      expect(callsTo(fetchMock, "GET", "/api/v1/cases").some((c) =>
        c.url.searchParams.get("inference_status") === "model_unavailable" && c.url.searchParams.get("crop_id") === "c-tom")).toBe(true),
    );
  });

  it("distinguishes no cases from no matches", async () => {
    mockFetch({ ...signedIn, "GET /api/v1/crops": () => jsonResponse([]), "GET /api/v1/cases": () => jsonResponse(page([])) });
    const user = userEvent.setup();
    renderRoute("/crop-doctor/cases");
    expect(await screen.findByRole("heading", { name: "No cases yet" })).toBeInTheDocument();
    await user.type(screen.getByLabelText("Search"), "CD-9");
    expect(await screen.findByRole("heading", { name: "No matching cases" })).toBeInTheDocument();
  });
});

describe("Crop Doctor AI result, assistant and Urdu", () => {
  const result = { decision: "accepted" as const, predicted_class: "early_blight", calibrated_confidence: 0.93, ood_score: -8,
    shortlist: [{ label: "early_blight", probability: 0.93 }], model_name: "crop_doctor_tomato", model_version: "1.0.0",
    analysed_at: "2026-11-23T09:00:00Z", image_count: 1, explanation_available: true, limits_note: "Decision support only." };
  const analysed = detail({ inference_status: "completed", status: "accepted",
    analysis: { inference_status: "completed", model_availability: "ready", error_code: null, message: "Analysis complete.", can_retry: false, result } });
  const info = { status: "ready", reason: "Model verified.", model_name: "crop_doctor_tomato", model_version: "1.0.0", arch: "mobilenet_v3_large",
    supported_crops: ["tomato"], classes: ["early_blight", "healthy"], metrics_ref: null,
    metrics_summary: { test: { n: 4000, accuracy: 0.9, macro_f1: 0.89 }, external_test: { n: 500, accuracy: 0.5, macro_f1: 0.4 } } };
  const explanation = { available: true, reason: null, method: "class_activation_map", target_class: "early_blight", decision: "accepted",
    note: "Aid only.", model_name: "crop_doctor_tomato", model_version: "1.0.0", limits_note: "Decision support only.",
    maps: [{ image: img, grid: [[1, 0], [0, 0]], crop_box: [0, 0, 1, 1],
      focus: { position: "upper left", strong_share_pct: 25, hotspots: 1, text_en: "The model focused mostly on the upper left.", text_ur: "ماڈل نے زیادہ تر اوپر بائیں پر توجہ دی۔", caveat: "x" } }] };
  const answer = { id: "a1", conversation_id: "c1", question: "Explain my result", retrieval_query: "q", language: "en", domain: null, crops: [],
    status: "answered", answer: "x", citations: [], n_passages: 0, retrieval_ms: 1, total_ms: 900, llm_provider: "groq", llm_model: "qwen/qwen3.8-27b",
    prompt_tokens: 1, completion_tokens: 1, feedback_rating: null, created_at: null,
    meta: { warnings: [], evidence_quality: "none", speech_text: "x", photo_sent: true,
      sections: { seen_in_photo: "SYNTHETIC: brown ringed spots.", explanation: "SYNTHETIC explanation [F].", next_steps: "SYNTHETIC: ask an expert." } } };
  const handlers = (user = testUser, asked: unknown[] = []) => ({
    ...signedIn,
    "POST /api/v1/auth/refresh": () => jsonResponse({ access_token: "tok", token_type: "bearer", expires_in: 900, user }),
    "GET /api/v1/auth/me": () => jsonResponse(user),
    "GET /api/v1/cases/case-1": () => jsonResponse(analysed),
    "GET /api/v1/cases/case-1/explanation": () => jsonResponse(explanation),
    "GET /api/v1/models/availability": () => jsonResponse(info),
    "GET /api/v1/knowledge/stats": () => jsonResponse({ providers: { llm: { enabled: true }, embeddings: {}, vision: { enabled: true, model: "qwen/qwen3.8-27b" } } }),
    "GET /api/v1/cases/case-1/assistant": () => jsonResponse(asked.length ? [answer] : []),
    "POST /api/v1/cases/case-1/assistant": ({ body }: { body: unknown }) => { asked.push(body); return jsonResponse(answer); },
  });  // prettier-ignore

  it("separates photo confidence from model test accuracy, explains the heatmap, and asks the assistant with photo opt-in", async () => {
    const asked: unknown[] = [];
    mockFetch(handlers(testUser, asked));
    const user = userEvent.setup();
    renderRoute("/crop-doctor/cases/case-1");
    expect(await screen.findByText("Early blight", { selector: "p" })).toBeInTheDocument();
    expect(screen.getByText("Confidence for this photo:")).toBeInTheDocument();
    expect(screen.getByText("93%", { selector: "strong" })).toBeInTheDocument();
    await user.click(await screen.findByText("How good is this model? (test results)"));
    expect(screen.getByText(/accuracy 90% · macro-F1 0.890/)).toBeInTheDocument();
    expect(screen.getByText(/not the confidence of your photo/)).toBeInTheDocument();
    expect(await screen.findByText("The model focused mostly on the upper left.")).toBeInTheDocument();
    await user.click(screen.getByLabelText(/Also let the AI look at my photo/));
    await user.click(screen.getByRole("button", { name: "Explain my result" }));
    expect(await screen.findByText("SYNTHETIC: brown ringed spots.")).toBeInTheDocument();
    expect(screen.getByText("AI description, not verified, not a diagnosis")).toBeInTheDocument();
    expect(asked[0]).toEqual({ language: "en", send_photo: true });
  });

  it("shows the Crop Doctor result and controls in Urdu for an Urdu profile", async () => {
    mockFetch(handlers({ ...testUser, locale: "ur" }));
    renderRoute("/crop-doctor/cases/case-1");
    expect(await screen.findByText("اگیتی جھلسا", { selector: "p" })).toBeInTheDocument();
    expect(screen.getByText("اس تصویر کے لیے اعتماد:")).toBeInTheDocument();
    expect(await screen.findByText("ماڈل نے زیادہ تر اوپر بائیں پر توجہ دی۔")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "میرا نتیجہ سمجھائیں" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Switch to English/ })).toBeInTheDocument();
  });
});
