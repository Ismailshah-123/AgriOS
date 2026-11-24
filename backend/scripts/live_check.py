"""Live end-to-end smoke check of every module against a RUNNING AgriOS API.

uv run python scripts/live_check.py [--api http://127.0.0.1:8000/api/v1]

Creates a fresh test account ("Live check (test data)") with one farm, field, tomato cycle,
soil tests, expenses and a Crop Doctor case, then exercises every module's API, including
ownership (a second account must get 404). Writes var/live_check_<stamp>.json. It never
reads .env and never touches other users' data.
"""

from __future__ import annotations

import argparse
import io
import json
import time
import urllib.error
import urllib.request
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
checks: list[dict[str, Any]] = []


class Client:
    def __init__(self, api: str) -> None:
        self.api, self.token = api, None

    def call(
        self,
        method: str,
        path: str,
        body: Any = None,
        raw: bytes | None = None,
        ctype: str | None = None,
    ) -> tuple[int, Any]:
        h = {"Origin": "http://localhost:5173", "Accept": "application/json"}
        data = raw
        if body is not None:
            data, h["Content-Type"] = json.dumps(body).encode(), "application/json"
        if ctype:
            h["Content-Type"] = ctype
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(self.api + path, data=data, headers=h, method=method)  # noqa: S310
        try:
            with urllib.request.urlopen(req, timeout=120) as r:  # noqa: S310
                txt = r.read()
                return r.status, json.loads(txt) if txt else None
        except urllib.error.HTTPError as e:
            txt = e.read()
            try:
                return e.code, json.loads(txt)
            except json.JSONDecodeError:
                return e.code, txt[:200].decode(errors="replace")


def check(name: str, ok: bool, detail: Any = "") -> None:
    checks.append({"check": name, "ok": bool(ok), "detail": detail})
    print(("PASS " if ok else "FAIL ") + name + (f"  {str(detail)[:160]}" if detail else ""))


def png() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (400, 300), (60, 140, 70)).save(buf, "PNG")
    return buf.getvalue()


def multipart(
    fields: dict[str, str], files: list[tuple[str, str, bytes, str]]
) -> tuple[bytes, str]:
    b = uuid.uuid4().hex
    out = io.BytesIO()
    for k, v in fields.items():
        out.write(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    for k, name, data, ct in files:
        out.write(
            f'--{b}\r\nContent-Disposition: form-data; name="{k}"; filename="{name}"\r\n'
            f"Content-Type: {ct}\r\n\r\n".encode()
            + data
            + b"\r\n"
        )
    out.write(f"--{b}--\r\n".encode())
    return out.getvalue(), f"multipart/form-data; boundary={b}"


def main() -> int:  # noqa: PLR0915
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8000/api/v1")
    api = ap.parse_args().api
    stamp = time.strftime("%Y%m%d%H%M%S")
    c, other = Client(api), Client(api)
    s, b = c.call("GET", "/ready")
    check("API ready (database)", s == 200, b)
    pw = "live-check-" + uuid.uuid4().hex[:12]
    s, b = c.call(
        "POST",
        "/auth/register",
        {
            "email": f"live-check-{stamp}@example.com",
            "password": pw,
            "full_name": "Live check (test data)",
        },
    )
    check("auth: register", s == 201, s)
    c.token = b["access_token"]
    s, b = other.call(
        "POST",
        "/auth/register",
        {
            "email": f"live-other-{stamp}@example.com",
            "password": pw,
            "full_name": "Live check other (test data)",
        },
    )
    other.token = b["access_token"]
    s, me = c.call("GET", "/auth/me")
    check("auth: me", s == 200 and me["role"] == "farmer", me.get("role"))

    s, farm = c.call(
        "POST",
        "/farms",
        {
            "name": "Live check farm (test data)",
            "province": "punjab",
            "district": "Lahore",
            "latitude": 31.52,
            "longitude": 74.36,
        },
    )
    check("farms: create", s == 201, s)
    s, fld = c.call(
        "POST",
        "/fields",
        {
            "farm_id": farm["id"],
            "name": "Live check field",
            "area": {"value": "2.5", "unit": "acre"},
            "area_origin": "farmer_entered",
        },
    )
    check("fields: create (2.5 acre)", s == 201, fld.get("area_ha") if s == 201 else fld)
    s, crops = c.call("GET", "/crops")
    tomato = next(x for x in crops if x["code"] == "tomato")
    sow = (date.today() - timedelta(days=60)).isoformat()
    s, cyc = c.call(
        "POST",
        "/crop-cycles",
        {"field_id": fld["id"], "crop_id": tomato["id"], "status": "active", "sowing_date": sow},
    )
    check("crop cycles: create active tomato", s == 201, s)
    s, _ = other.call("GET", f"/fields/{fld['id']}")
    check("ownership: other user gets 404 for my field", s == 404, s)

    soil = {
        "field_id": fld["id"],
        "sampled_on": date.today().isoformat(),
        "data_origin": "measured",
        "ph": "8.1",
        "ph_method": "water_1_1",
        "ec_ds_m": "3.2",
        "ec_method": "saturated_paste_ece",
        "organic_matter_pct": "0.8",
        "phosphorus_mg_kg": "7.5",
        "phosphorus_method": "olsen",
        "potassium_mg_kg": "150",
        "lab_name": "Live check lab (test data)",
    }
    s, obs = c.call("POST", "/soil-observations", soil)
    check("soil: create test with units", s == 201, s)
    s, up = c.call("PATCH", f"/soil-observations/{obs['id']}", {"ph": "8.0"})
    check(
        "soil: edit pH",
        s == 200 and str(up.get("ph", "")).startswith("8.0"),
        up.get("ph") if isinstance(up, dict) else up,
    )
    s, extra = c.call("POST", "/soil-observations", {**soil, "ph": "7.0"})
    s, _ = c.call("DELETE", f"/soil-observations/{extra['id']}")
    check("soil: delete", s == 204, s)
    s, summ = c.call("GET", f"/fields/{fld['id']}/soil-summary")
    check("soil: summary/history", s == 200, list(summ)[:6] if isinstance(summ, dict) else summ)

    s, w = c.call("GET", f"/weather?field_id={fld['id']}")
    ok = s == 200 and isinstance(w, dict)
    check(
        "weather: Open-Meteo forecast",
        ok,
        {k: w.get(k) for k in ("status", "provider")} if ok else w,
    )
    s, wd = c.call("GET", f"/fields/{fld['id']}/water-demand")
    check(
        "irrigation: FAO-56 ETc water demand",
        s == 200,
        wd.get("totals") if isinstance(wd, dict) else wd,
    )

    s, _ = c.call(
        "POST",
        "/expenses",
        {"crop_cycle_id": cyc["id"], "category": "seed", "amount_pkr": "12000", "incurred_on": sow},
    )
    check("economics: expense", s == 201, s)
    s, _ = c.call(
        "POST",
        "/harvest-sales",
        {
            "crop_cycle_id": cyc["id"],
            "recorded_on": date.today().isoformat(),
            "quantity_kg": "500",
            "price_pkr_per_kg": "60",
        },
    )
    check("economics: harvest sale", s == 201, s)
    s, ec = c.call("GET", f"/crop-cycles/{cyc['id']}/economics")
    prof = ec.get("summary", {}).get("profit_pkr") if isinstance(ec, dict) else None
    check("economics: profit = 30000 - 12000", s == 200 and prof == "18000.00", prof)
    s, fz = c.call("GET", f"/crop-cycles/{cyc['id']}/fertilizer")
    check(
        "fertilizer: refuses without reviewed table",
        s == 200 and "refus" in json.dumps(fz),
        fz.get("status") if isinstance(fz, dict) else fz,
    )

    s, run = c.call(
        "POST",
        "/agent/runs",
        {"message": "Give me a field condition report", "field_id": fld["id"]},
    )
    check("agents: field report run", s == 201, run.get("status") if isinstance(run, dict) else run)
    s, run2 = c.call(
        "POST",
        "/agent/runs",
        {"message": "set farm location to 31.50, 74.30", "field_id": fld["id"]},
    )
    acts = run2.get("actions", []) if isinstance(run2, dict) else []
    check(
        "agents: write needs approval (pending)",
        bool(acts) and acts[0]["status"] == "pending",
        [a["status"] for a in acts],
    )
    if acts:
        s, rj = c.call("POST", f"/agent/actions/{acts[0]['id']}/reject")
        check(
            "agents: reject pending write",
            s == 200 and rj["status"] == "rejected",
            rj.get("status"),
        )

    body, ct = multipart(
        {"crop_cycle_id": cyc["id"], "plant_part": "leaf", "symptoms": "spots"},
        [("images", "leaf.png", png(), "image/png")],
    )
    s, case = c.call("POST", "/cases", raw=body, ctype=ct)
    check("crop doctor: create case with photo", s == 201, s)
    st = None
    for _ in range(20):
        time.sleep(2)
        s, an = c.call("GET", f"/cases/{case['id']}/analysis")
        st = an.get("inference_status") if isinstance(an, dict) else None
        if st not in ("pending", "queued", "running", None):
            break
    s, avail = c.call("GET", "/models/availability")
    check(
        "crop doctor: worker processed case",
        st not in ("pending", "queued", "running", None),
        {"inference_status": st, "model": avail},
    )
    s, _ = other.call("GET", f"/cases/{case['id']}")
    check("ownership: other user gets 404 for my case", s == 404, s)

    s, ov = c.call("GET", "/overview")
    check("dashboard: overview", s == 200, list(ov)[:6] if isinstance(ov, dict) else ov)
    s, an = c.call("GET", "/analytics")
    check("dashboard: analytics", s == 200, list(an)[:6] if isinstance(an, dict) else an)

    s, ks = c.call("GET", "/knowledge/stats")
    check(
        "knowledge: library stats",
        s == 200 and ks["chunks"] > 0,
        {"sources": ks.get("searchable_sources"), "chunks": ks.get("chunks")},
    )
    s, ka = c.call("POST", "/knowledge/ask", {"question": "Summarise the soil test for my field"})
    fc = (ka.get("meta") or {}).get("farm_context") or {} if isinstance(ka, dict) else {}
    vals = fc.get("fields", [{}])[0].get("latest_soil_test", {}) if fc.get("fields") else {}
    check(
        "knowledge: farm-context answer uses own soil test",
        s == 200 and bool(vals),
        {"status": ka.get("status"), "soil": vals.get("values") if vals else None},
    )
    s, kb = other.call(
        "POST", "/knowledge/ask", {"question": "Summarise the soil test for my field"}
    )
    check(
        "knowledge: other user sees none of my records",
        s == 200 and "Live check field" not in json.dumps(kb),
        kb.get("status"),
    )
    s, kc = c.call("POST", "/knowledge/ask", {"question": "What causes early blight on tomato?"})
    check(
        "knowledge: cited answer",
        s == 200 and kc["status"] in ("answered", "extractive") and kc["citations"],
        {"status": kc.get("status"), "n_citations": len(kc.get("citations", []))},
    )

    out = ROOT / "var" / f"live_check_{stamp}.json"
    out.write_text(
        json.dumps({"stamp": stamp, "api": api, "checks": checks}, indent=1), encoding="utf-8"
    )
    n_ok = sum(x["ok"] for x in checks)
    print(f"{n_ok}/{len(checks)} passed -> {out}")
    return 0 if n_ok == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
