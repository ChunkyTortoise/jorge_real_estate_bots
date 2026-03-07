#!/usr/bin/env bash
set -euo pipefail

# Run the repo-side production-finalization helpers and store outputs in docs/.
#
# Required env vars for full execution:
#   JORGE_LIVE_URL
#   ADMIN_API_KEY
#   JORGE_CONTACT_ID
#   DATABASE_URL
# Optional env vars for GHL contract validation:
#   GHL_TAGS_JSON
#   GHL_FIELDS_JSON
#   GHL_WORKFLOWS_JSON
# Or use live read-only GHL fetch with:
#   GHL_API_KEY
#   GHL_LOCATION_ID
# Optional dry-run GHL sync plan:
#   python3 scripts/sync_ghl_contract.py --ghl-api-key "$GHL_API_KEY" --location-id "$GHL_LOCATION_ID"
#
# Example:
#   JORGE_LIVE_URL=https://jorge-realty-ai-xxdf.onrender.com \
#   ADMIN_API_KEY=... \
#   JORGE_CONTACT_ID=abc123 \
#   DATABASE_URL=postgresql+asyncpg://... \
#   bash scripts/run_production_finalization.sh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOCS_DIR="$ROOT_DIR/docs"
LIVE_URL="${JORGE_LIVE_URL:-https://jorge-realty-ai-xxdf.onrender.com}"
CONTACT_ID="${JORGE_CONTACT_ID:-}"

echo "== Jorge Production Finalization =="
echo "Root: $ROOT_DIR"
echo "Live URL: $LIVE_URL"
echo

echo "== App readiness report =="
python3 "$ROOT_DIR/scripts/production_readiness_report.py" \
  --base-url "$LIVE_URL" \
  ${ADMIN_API_KEY:+--admin-key "$ADMIN_API_KEY"} \
  ${CONTACT_ID:+--contact-id "$CONTACT_ID"} \
  --output "$DOCS_DIR/production_readiness_report.md" || true
echo "Wrote: $DOCS_DIR/production_readiness_report.md"
echo

if [[ -n "${DATABASE_URL:-}" ]]; then
  echo "== Database schema report =="
  python3 "$ROOT_DIR/scripts/check_conversation_schema.py" \
    --database-url "$DATABASE_URL" \
    --json > "$DOCS_DIR/conversation_schema_report.json" || true
  echo "Wrote: $DOCS_DIR/conversation_schema_report.json"
else
  echo "== Database schema report =="
  echo "Skipped: DATABASE_URL not set"
fi
echo

if [[ -n "${GHL_TAGS_JSON:-}" || -n "${GHL_FIELDS_JSON:-}" || -n "${GHL_WORKFLOWS_JSON:-}" || ( -n "${GHL_API_KEY:-}" && -n "${GHL_LOCATION_ID:-}" ) ]]; then
  echo "== GHL contract validation =="
  python3 "$ROOT_DIR/scripts/validate_ghl_contract.py" \
    ${GHL_TAGS_JSON:+--tags-json "$GHL_TAGS_JSON"} \
    ${GHL_FIELDS_JSON:+--fields-json "$GHL_FIELDS_JSON"} \
    ${GHL_WORKFLOWS_JSON:+--workflows-json "$GHL_WORKFLOWS_JSON"} \
    ${GHL_API_KEY:+--ghl-api-key "$GHL_API_KEY"} \
    ${GHL_LOCATION_ID:+--location-id "$GHL_LOCATION_ID"} \
    --output "$DOCS_DIR/ghl_contract_validation_report.md" || true
  echo "Wrote: $DOCS_DIR/ghl_contract_validation_report.md"
else
  echo "== GHL contract validation =="
  echo "Skipped: no GHL_*_JSON export paths set"
fi
echo

if [[ -n "${GHL_API_KEY:-}" && -n "${GHL_LOCATION_ID:-}" ]]; then
  echo "== GHL legacy contract review =="
  python3 "$ROOT_DIR/scripts/review_ghl_legacy_contract.py" \
    --ghl-api-key "$GHL_API_KEY" \
    --location-id "$GHL_LOCATION_ID" \
    --output "$DOCS_DIR/ghl_legacy_contract_review.md" || true
  echo "Wrote: $DOCS_DIR/ghl_legacy_contract_review.md"
else
  echo "== GHL legacy contract review =="
  echo "Skipped: GHL_API_KEY and GHL_LOCATION_ID not both set"
fi
echo

cat <<EOF
Next manual steps:
1. Fill out $DOCS_DIR/JORGE_GHL_WORKFLOW_INVENTORY.md
2. Review $DOCS_DIR/ghl_legacy_contract_review.md and classify high-risk legacy tags/fields
3. Review / optionally apply python3 $ROOT_DIR/scripts/sync_ghl_contract.py --ghl-api-key "\$GHL_API_KEY" --location-id "\$GHL_LOCATION_ID"
4. Execute $DOCS_DIR/JORGE_LIVE_VALIDATION_CHECKLIST.md
5. Complete $DOCS_DIR/JORGE_PRODUCTION_HANDOFF_SIGNOFF.md
EOF
