# Soil, weather, risk and irrigation methods
Summary: data handling and the documented rules behind Soil Intelligence, Weather Intelligence, the agricultural risk engine and the FAO-56 irrigation foundation. Every rule names its source; anything without a reviewed source is reported as `not_evaluated`, never guessed.

## 1. Soil data and interpretation (`backend/app/soil/`)
- One row = one soil test of a field on a date (`soil_observations`). Origin: `measured` (lab report, lab name required) or `farmer_entered` (field kit/manual).
- Stored with units: pH (pH units), EC (dS/m), organic matter / organic carbon / total N (%), P, K, Ca, Mg, S, Zn, Fe, B (mg/kg), CEC (cmol(+)/kg), texture (USDA class), depth (cm), lab name/reference, and method: pH method, EC method, P method, plus a free-text lab method per secondary/micronutrient (`nutrient_methods`, migration 0007).
- Missing values stay NULL and are listed as missing; they are never replaced by 0.
- Interpretation (general international guidance, **not Pakistan-specific fertility tables**):
  - pH reaction classes — USDA Soil Survey Manual (Handbook 18, ch. 3); only for water pH methods.
  - Salinity classes on ECe — USDA Soil Survey Manual; other EC ratios are not converted (texture-dependent).
  - Crop salt tolerance (tomato threshold 2.5 dS/m, slope 9.9 %/dS/m) — Maas & Hoffman (1977) as tabulated in FAO Paper 29.
  - pH ≥ 8.5 sodicity warning — USDA Handbook 60.
  - OM, OC, N, P, K, Ca, Mg, S, Zn, Fe, B, CEC: stored and shown, listed as `not_evaluated` (no reviewed fertility classification for the lab method and region is stored).
- No fertilizer or amendment quantity is ever produced (hard rule 2).

## 2. Weather provider (`backend/app/weather/provider.py`)
- Open-Meteo forecast API (`https://api.open-meteo.com/v1/forecast`), no API key. Attribution shown in the UI: Open-Meteo, data CC BY 4.0; the free tier is for non-commercial use (a commercial deployment needs a paid plan or another provider).
- Variables: current temperature, RH, precipitation, wind, weather code; hourly temperature, RH, precipitation, precipitation probability; daily max/min temperature, precipitation sum and probability, max wind, FAO-56 ET0.
- Provider abstraction: any provider returning the normalised dict can replace it; missing fields stay `None`.
- Location: farm latitude/longitude stored to 0.01° (~1 km). Missing coordinates → `unavailable / location_missing` (no request, nothing invented).
- Cache: one snapshot per provider+location; fresh for 30 min; on provider error a snapshot < 24 h old is returned as `stale` with a visible warning; otherwise `unavailable / provider_error`. Retrieval time and age are returned and displayed.
- Tests use a synthetic FakeProvider; no test calls the network.

## 3. Agricultural risk indicators (`backend/app/weather/indicators.py`)
Each indicator returns level, message, evidence, time window, basis, source, review status and limitations. Indicators describe weather only; none is a disease diagnosis.

| Indicator | Rule | Source |
|---|---|---|
| frost_risk | daily min ≤ 0 °C | physical definition |
| late_blight_smith_period | 2 consecutive days, min ≥ 10 °C and ≥ 11 h RH ≥ 90 % | Smith (1956), Plant Pathology 5 |
| rain_vs_et0 | 3-day forecast rain vs 3-day ET0 | FAO-56 (method reference) |
| heavy_rainfall | daily rain: heavy 64.5–115.5, very heavy 115.6–204.4, extremely heavy ≥ 204.5 mm | India Meteorological Department categories (regional, not PMD) |
| high_wind | daily max wind: strong breeze ≥ 39, near gale ≥ 50, gale ≥ 62 km/h | Beaufort scale (WMO) |
| dry_spell | longest run of days < 1 mm (info only) | ETCCDI dry-day / CDD definition |
| rainfall_accumulation | forecast total (info only) | arithmetic |
| heat_stress, spray window | **not evaluated** | no reviewed crop-specific threshold yet |

## 4. Irrigation foundation (`backend/app/irrigation/`)
- ETc = Kc × ET0 (FAO-56 Eq. 56). Kc constant in initial and mid-season stages, linear in development and late season (FAO-56 Fig. 25).
- Crops: tomato (Kc 0.60 / 1.15 / 0.70–0.90; stages 30/40/40/25 d, Table 11 arid-region entry) and cotton (0.35 / 1.15–1.20 / 0.50–0.70; 30/50/60/55 d, Table 11 Mar–May entry listing Pakistan). Ranges are carried as low/high ETc. Values marked `transcribed_from_FAO56_pending_expert_review`; not climate-adjusted.
- Planting date = crop cycle sowing date (enter the transplanting date for transplanted tomato). Outside the FAO-56 season no Kc is produced.
- Effective rainfall is **not** subtracted (no defensible method/inputs configured); gross forecast rain is shown separately. Estimated demand is labelled `inferred` and is never presented as soil moisture. No equipment is controlled.
- Missing inputs (active cycle, sowing date, coordinates, ET0) are returned in `missing_information`.
