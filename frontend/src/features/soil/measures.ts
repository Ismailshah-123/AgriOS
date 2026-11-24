/** Measures with their unit. Empty input = not measured (sent as null, never 0). */
export const SOIL_MEASURES: { key: string; label: string; unit: string; method?: string }[] = [
  { key: "ph", label: "pH", unit: "pH units", method: "ph_method" },
  { key: "ec_ds_m", label: "EC", unit: "dS/m", method: "ec_method" },
  { key: "organic_matter_pct", label: "Organic matter", unit: "%" },
  { key: "organic_carbon_pct", label: "Organic carbon", unit: "%" },
  { key: "nitrogen_total_pct", label: "Total nitrogen", unit: "%" },
  { key: "phosphorus_mg_kg", label: "Phosphorus (P)", unit: "mg/kg", method: "phosphorus_method" },
  { key: "potassium_mg_kg", label: "Potassium (K)", unit: "mg/kg" },
  { key: "calcium_mg_kg", label: "Calcium (Ca)", unit: "mg/kg" },
  { key: "magnesium_mg_kg", label: "Magnesium (Mg)", unit: "mg/kg" },
  { key: "sulfur_mg_kg", label: "Sulfur (S)", unit: "mg/kg" },
  { key: "zinc_mg_kg", label: "Zinc (Zn)", unit: "mg/kg" },
  { key: "iron_mg_kg", label: "Iron (Fe)", unit: "mg/kg" },
  { key: "boron_mg_kg", label: "Boron (B)", unit: "mg/kg" },
  { key: "cec_cmol_kg", label: "CEC", unit: "cmol(+)/kg" },
];
