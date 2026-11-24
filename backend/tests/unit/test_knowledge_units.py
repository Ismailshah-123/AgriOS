"""Unit tests: extraction formats, query understanding, validation guards (no database)."""

import io

import docx
import pytest

from app.knowledge import extract, generation, query
from app.knowledge.retrieval import Passage


def test_markdown_and_html_keep_sections() -> None:
    md = extract.extract("md", b"# Soil salinity\n\nSalt harms roots.\n\n## Drainage\n\nDrain it.")
    assert [(s.heading, s.text) for s in md] == [
        ("Soil salinity", "Salt harms roots."),
        ("Drainage", "Drain it."),
    ]
    html = b"<html><script>alert(1)</script><h2>Drip irrigation</h2><p>Drip saves water.</p></html>"
    out = extract.extract("html", html)
    assert out[0].heading == "Drip irrigation" and "alert" not in out[0].text


def test_docx_headings_and_tables() -> None:
    d = docx.Document()
    d.add_heading("Wheat sowing", level=1)
    d.add_paragraph("Sow in November.")
    t = d.add_table(rows=1, cols=2)
    t.rows[0].cells[0].text, t.rows[0].cells[1].text = "stage", "tillering"
    buf = io.BytesIO()
    d.save(buf)
    out = extract.extract(extract.detect_format("w.docx", buf.getvalue()), buf.getvalue())
    assert out[0].heading == "Wheat sowing" and out[0].text == "Sow in November."
    assert out[-1].heading == "Table 1" and "tillering" in out[-1].text


def test_csv_rows_keep_column_names() -> None:
    out = extract.extract("csv", b"crop,kc_mid\ntomato,1.15\n")
    assert out[0].text == "crop: tomato; kc_mid: 1.15"


@pytest.mark.parametrize(
    ("name", "data", "code"),
    [
        ("a.exe", b"MZ", "unsupported_format"),
        ("a.pdf", b"hello", "content_does_not_match_extension"),
        ("a.docx", b"%PDF-1.4", "content_does_not_match_extension"),
        ("a.txt", b"\x00\x01binary", "content_does_not_match_extension"),
    ],
)
def test_file_type_is_checked_from_content(name: str, data: bytes, code: str) -> None:
    with pytest.raises(extract.ExtractionError, match=code):
        extract.detect_format(name, data)


def test_query_language_glossary_domain_farm_intent() -> None:
    ur = query.analyse("ٹماٹر کے پتوں پر پیلے دھبے کیوں ہیں؟")
    assert ur.language == "ur" and ur.crops == ["tomato"]
    assert "plant_protection" in ur.domains and "yellow" in ur.retrieval_terms
    roman = query.analyse("mere tamatar ke patte peelay kyun hain")
    assert roman.language == "ur-Latn" and roman.farm_intent and roman.crops == ["tomato"]
    en = query.analyse("How do I calculate profit per acre for a rice farm?")
    assert en.language == "en" and en.domains[0] == "economics_business" and not en.farm_intent
    assert query.analyse("Summarise the soil tests for my field").farm_intent
    assert query.analyse("my cow has fever").veterinary
    assert query.is_ambiguous("help", query.analyse("help"))


def _p(text: str) -> Passage:
    src = {"title": "T", "publisher": "P", "year": None}
    return Passage(chunk_id=None, text=text, page=1, section=None, rank=0.1, source=src)  # type: ignore[arg-type]


def test_validate_citations_dose_and_grounding() -> None:
    ps = [_p("Late blight spreads in cool wet weather and destroys tomato leaves quickly.")]
    v = generation.validate(
        "Late blight spreads in cool wet weather on tomato leaves [S1] [S4].",
        ps,
        has_farm=False,
        language="en",
    )
    assert v.cited == [1] and "invalid_citation_removed" in v.warnings and v.grounded_share == 1.0
    d = generation.validate(
        "Apply 2.5 kg/acre of copper fungicide [S1].", ps, has_farm=False, language="en"
    )
    assert "2.5 kg/acre" not in d.text and "dose_removed" in d.warnings
    assert generation.validate("INSUFFICIENT_EVIDENCE", ps, has_farm=False, language="en").abstained
    off = generation.validate(
        "Bananas need volcanic soils with heavy magnesium supplementation always [S1].",
        ps,
        has_farm=False,
        language="en",
    )
    assert off.grounded_share == 0.0
    assert generation.speech_text("Yes [S1] **now** [F]") == "Yes now"


def test_rewrite_parsing_tolerates_fences() -> None:
    q, clar = generation.parse_rewrite(
        '```json\n{"query": "tomato blight", "needs_clarification": false}\n```'
    )
    assert (q, clar) == ("tomato blight", None)
    assert generation.parse_rewrite("not json") == (None, None)


def test_citation_styles_are_normalised() -> None:
    t = generation.normalise_citations("Early‑blight【S1】【S6】 and mosaic [S2, S3] (S4) [S5; F].")
    assert t == "Early-blight[S1][S6] and mosaic [S2] [S3] [S4] [S5] [F]."


def test_rate_limit_retries_then_uses_fallback_model(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.knowledge import providers

    llm = providers.OpenAICompatibleLLM("groq", "http://x", "big", "k", 5, fallback="small")
    calls: list[str] = []

    def fake_post(model: str, *_: object) -> dict:
        calls.append(model)
        if model == "big":
            raise providers._RateLimited(60)  # long wait: go straight to the fallback
        return {"choices": [{"message": {"content": "ok"}}], "model": model}

    monkeypatch.setattr(llm, "_post", fake_post)
    r = llm.chat([{"role": "user", "content": "q"}], max_tokens=10)
    assert (calls, r.model, r.text) == (["big", "small"], "small", "ok")
    monkeypatch.setattr(llm, "_post", lambda *_: (_ for _ in ()).throw(providers._RateLimited(99)))
    with pytest.raises(providers.LLMError, match="llm_http_429"):
        llm.chat([{"role": "user", "content": "q"}], max_tokens=10)


def test_advisory_sentences_are_not_scored() -> None:
    ps = [_p("Early blight causes brown concentric spots on older tomato leaves.")]
    v = generation.validate(
        "Early blight causes brown concentric spots on older tomato leaves [S1]. "
        "Please consult your local extension officer for a confirmed diagnosis.",
        ps,
        has_farm=False,
        language="en",
    )
    assert v.grounded_share == 1.0


def test_citations_after_full_stop_and_headings_are_handled() -> None:
    ps = [_p("Leaching with good quality water flushes soluble salts out of the root zone.")]
    v = generation.validate(
        "**Managing salinity**\n- Leaching with good quality water flushes salts from the root "
        "zone. [S1]",
        ps,
        has_farm=False,
        language="en",
    )
    assert v.grounded_share == 1.0


def test_dose_requests_and_quoted_rates() -> None:
    assert query.analyse("How much copper fungicide per acre should I spray?").dose_request
    assert query.analyse("ٹماٹر پر کتنی کھاد ڈالیں؟").dose_request
    assert not query.analyse("How does copper affect late blight?").dose_request
    t, changed = generation.redact_doses("limit is 6 kilograms per hectare (5.4 lb/acre)/year")
    assert changed and "6 kilograms" not in t and "5.4 lb/acre" not in t
