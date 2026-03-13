/**
 * RecallAlert — Supabase Vehicle Recall Query
 * Drop this <script> block into index.html to replace fetchVehicles()
 * once the GitHub Actions pipeline has populated the vehicle_recalls table.
 *
 * Supabase REST API needs no backend — queries run direct from the browser
 * using the public anon key (read-only via Row Level Security).
 */

const SUPA_URL = "https://eyprbgcvfsmlarxljszx.supabase.co";
const SUPA_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV5cHJiZ2N2ZnNtbGFyeGxqc3p4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMyMzg3MTEsImV4cCI6MjA4ODgxNDcxMX0.AVppvjMh36PXFusz1VI4s7Kk1JXDhsRazf2MHqXhTfU";

async function fetchVehiclesFromSupabase(q, page = 0, perPage = 20) {
  const offset = page * perPage;
  let url = `${SUPA_URL}/rest/v1/vehicle_recalls?`;

  const params = new URLSearchParams({
    select: "campaign_number,make,model,model_year,manufacturer,component,defect_summary,consequence,remedy,recall_date,potentially_affected,recall_type",
    order:  "recall_date.desc.nullslast",
    limit:  String(perPage),
    offset: String(offset),
  });

  if (q) {
    // Full-text search across make, model, component, defect summary
    params.append("or", `make.ilike.*${q}*,model.ilike.*${q}*,component.ilike.*${q}*,defect_summary.ilike.*${q}*`);
  }

  url += params.toString();

  const resp = await fetch(url, {
    headers: {
      "apikey":        SUPA_KEY,
      "Authorization": `Bearer ${SUPA_KEY}`,
      "Accept":        "application/json",
      // Ask for total count header so we can show pagination
      "Prefer":        "count=exact",
    }
  });

  if (!resp.ok) throw new Error(`Supabase error: ${resp.status}`);

  const data = await resp.json();
  const totalCount = parseInt(resp.headers.get("content-range")?.split("/")[1] || "0");

  return { rows: data, total: totalCount };
}

function normalizeSupabaseRow(r) {
  const consequence = (r.consequence || "").toLowerCase();
  const cls = consequence.match(/death|fatal|fire|crash|rollover|stall/)
    ? "Class I"
    : consequence.match(/injur|burn|lacerat|fractur|risk/)
    ? "Class II" : "Class III";

  const vehicle = [r.make, r.model, r.model_year].filter(Boolean).join(" ");

  return {
    recalling_firm:          vehicle || r.manufacturer || "Vehicle",
    product_description:     r.component || "",
    reason_for_recall:       r.defect_summary || "—",
    classification:          cls,
    status:                  "Ongoing",
    recall_initiation_date:  (r.recall_date || "").replace(/-/g, ""),  // "2023-01-15" → "20230115"
    recall_number:           r.campaign_number || "",
    distribution_pattern:    "Nationwide",
    _source:                 "NHTSA",
    _cpsc:                   false,
    _consequence:            r.consequence || "",
    _remedy:                 r.remedy || "",
    _affected:               r.potentially_affected,
  };
}

// Replace fetchVehicles() with this version once pipeline is live
async function fetchVehicles() {
  showSkeleton();
  const q = currentQ.trim();
  try {
    const { rows, total } = await fetchVehiclesFromSupabase(q, currentPage, PER_PAGE);
    const cards = rows.map(normalizeSupabaseRow);

    if (!cards.length) {
      showEmpty("No vehicle recalls found", "Try 'Toyota', 'brake', or 'airbag'.");
      return;
    }

    totalResults = total;
    window._vehicleCards = null;  // not caching — Supabase handles pagination
    renderResults(cards);
    updatePagination();
  } catch (e) {
    console.error("Supabase vehicle fetch error:", e);
    showEmpty("Could not load vehicle recalls", "Check your connection and try again.");
  }
}
