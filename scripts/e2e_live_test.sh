#!/usr/bin/env bash
# E2E Live Acceptance Test — Jorge GHL Bots
# Uses /test/seller and /test/buyer for automated assertions (no GHL required)
# Uses /api/ghl/webhook for real SMS to phone 3109820492
#
# Run:  bash scripts/e2e_live_test.sh
#       bash scripts/e2e_live_test.sh --no-sms    (skip SMS steps)
set -euo pipefail

# ─── Config ──────────────────────────────────────────────────────────────────
BASE_URL="${JORGE_LIVE_URL:-https://jorge-realty-ai-xxdf.onrender.com}"
CONTACT_ID="prX3fC1c7UaCjUzwdeyu"
LOCATION_ID="${GHL_LOCATION_ID:-3xt4qayAh35BlDLaUv7P}"
PHONE="3109820492"
STEP_DELAY=1    # seconds between test-endpoint calls (fast = same Render instance)
SMS_DELAY=8     # seconds between real webhook calls (SMS delivery time)

# Unique contact IDs so state doesn't bleed between test runs
TS=$(date +%s)
BUYER_CID="e2e-buyer-${TS}"
SELLER_CID="e2e-seller-${TS}"

NO_SMS=false
[[ "${1:-}" == "--no-sms" ]] && NO_SMS=true

# ─── Counters ────────────────────────────────────────────────────────────────
PASS=0
FAIL=0
WARN=0

# ─── Helpers ─────────────────────────────────────────────────────────────────
green()  { printf "\033[32m%s\033[0m\n" "$*"; }
red()    { printf "\033[31m%s\033[0m\n" "$*"; }
yellow() { printf "\033[33m%s\033[0m\n" "$*"; }
blue()   { printf "\033[34m%s\033[0m\n" "$*"; }
bold()   { printf "\033[1m%s\033[0m\n" "$*"; }

pass() { PASS=$((PASS+1)); green "  ✓ $*"; }
fail() { FAIL=$((FAIL+1)); red   "  ✗ $*"; }
warn() { WARN=$((WARN+1)); yellow "  ⚠ $*"; }

# ─── Test-endpoint call ───────────────────────────────────────────────────────
# send_test BOT MESSAGE CID [RESET]
send_test() {
  local bot="$1" msg="$2" cid="$3" reset="${4:-false}"
  local payload
  payload=$(python3 -c "
import json, sys
d = {'message': sys.argv[1], 'contact_id': sys.argv[2], 'reset': sys.argv[3] == 'true'}
if sys.argv[4] == 'buyer':
    d['buyer_name'] = 'Test Lead'
print(json.dumps(d))
" "$msg" "$cid" "$reset" "$bot")
  curl -s -X POST "$BASE_URL/test/$bot" \
    -H "Content-Type: application/json" \
    -d "$payload" \
    --max-time 45 2>/dev/null
}

# ─── Real webhook call (nested GHL format) ───────────────────────────────────
# send_webhook BOT_TYPE MESSAGE
send_webhook() {
  local bot_type="$1" msg="$2"
  local payload
  payload=$(python3 -c "
import json, sys
print(json.dumps({
  'type': 'MESSAGE_RECEIVED',
  'contactId': '$CONTACT_ID',
  'locationId': '$LOCATION_ID',
  'message': {'type': 'SMS', 'body': sys.argv[1], 'direction': 'inbound'},
  'contact': {
    'contactId': '$CONTACT_ID',
    'phone': '$PHONE',
    'tags': [],
    'customFields': {'bot_type': sys.argv[2]}
  }
}))
" "$msg" "$bot_type")
  local response http_code body
  response=$(curl -s -w "\n__HTTP_CODE__:%{http_code}" \
    -X POST "$BASE_URL/api/ghl/webhook" \
    -H "Content-Type: application/json" \
    -d "$payload" \
    --max-time 60 2>/dev/null)
  http_code=$(echo "$response" | grep "__HTTP_CODE__:" | sed 's/__HTTP_CODE__://')
  body=$(echo "$response" | sed '/^__HTTP_CODE__:/d')
  echo "$http_code|$body"
}

# ─── Assertion helpers ────────────────────────────────────────────────────────
field() {
  # field BODY KEY
  echo "$1" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('$2',''))" 2>/dev/null || echo ""
}

assert_contains() {
  local label="$1" text="$2" pattern="$3"
  if echo "$text" | grep -qiE "$pattern" 2>/dev/null; then
    pass "$label: contains '$pattern'"
  else
    fail "$label: expected '$pattern' — got: ${text:0:120}"
  fi
}

assert_not_contains() {
  local label="$1" text="$2"
  shift 2
  local found=""
  for term in "$@"; do
    if echo "$text" | grep -qiE "$term" 2>/dev/null; then
      found="$term"
      break
    fi
  done
  if [[ -n "$found" ]]; then
    fail "$label: forbidden term '$found' found in response"
  else
    pass "$label: no forbidden terms"
  fi
}

assert_cash_offer() {
  local label="$1" text="$2"
  # $430K–$440K range in various formats
  if echo "$text" | python3 -c "
import sys, re
t = sys.stdin.read()
# Look for 430000-440000 in various notations
patterns = [
    r'\\\$4[34][0-9][,.]?[0-9]*[kK]',    # \$430k–\$440k
    r'\\\$4[34][0-9],?000',               # \$430,000–\$440,000
    r'4[34][0-9],?000',                    # bare number
    r'4[34][0-9][kK]',                     # 430k–440k bare
]
for p in patterns:
    if re.search(p, t, re.IGNORECASE):
        sys.exit(0)
sys.exit(1)
" 2>/dev/null; then
    pass "$label: cash offer in \$430K–\$440K range found"
  else
    fail "$label: cash offer ~\$435K NOT found — got: ${text:0:200}"
  fi

  if echo "$text" | grep -qiE "2.?3 weeks|two.?to.?three weeks" 2>/dev/null; then
    pass "$label: '2-3 weeks' timeline present"
  else
    fail "$label: '2-3 weeks' NOT found — got: ${text:0:200}"
  fi

  if echo "$text" | grep -qiE "no repair|as.?is|without repair|no fix" 2>/dev/null; then
    pass "$label: 'no repairs' language present"
  else
    fail "$label: 'no repairs' NOT found — got: ${text:0:200}"
  fi
}

sms_prompt() {
  local step="$1" expected="$2"
  yellow "  📱 SMS [$step]: Check AirDroid (phone $PHONE) — $expected"
}

# ─── Pre-flight ───────────────────────────────────────────────────────────────
preflight() {
  bold ""
  bold "═══════════════════════════════════════"
  bold " PRE-FLIGHT"
  bold "═══════════════════════════════════════"
  local resp
  resp=$(curl -s "$BASE_URL/health" --max-time 15 2>/dev/null || echo "{}")
  if echo "$resp" | grep -q '"healthy"' 2>/dev/null; then
    pass "GET /health → healthy"
  else
    fail "GET /health failed ($resp)"
    exit 1
  fi

  # Check if /test endpoints exist
  local check
  check=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/test/buyer" \
    -H "Content-Type: application/json" \
    -d '{"message":"ping","contact_id":"preflight-check","reset":true}' --max-time 10 2>/dev/null)
  if [[ "$check" == "200" ]]; then
    pass "/test/buyer endpoint reachable"
  else
    warn "/test/buyer returned $check — test-endpoint flow may fail"
  fi
}

# ─── Buyer flow ───────────────────────────────────────────────────────────────
buyer_flow() {
  bold ""
  bold "═══════════════════════════════════════"
  bold " BUYER BOT FLOW (automated)"
  bold "═══════════════════════════════════════"
  echo "  Contact ID: $BUYER_CID"
  echo ""

  local r resp temp turn

  # B-Q0
  blue "  [B-Q0] Initial buyer message"
  r=$(send_test buyer "Hi, I am interested in buying a home in the area" "$BUYER_CID" true)
  resp=$(field "$r" "response"); turn=$(field "$r" "turn")
  [[ -n "$resp" ]] && pass "B-Q0: got response (turn $turn)" || fail "B-Q0: no response"
  assert_not_contains "B-Q0 no seller terms" "$resp" \
    "condition" "cash offer" "no repairs" "2-3 weeks" "what.*worth" "zestimate"
  echo "    BOT: $resp" | head -c 200; echo
  sleep "$STEP_DELAY"

  # B-Q1
  echo ""
  blue "  [B-Q1] Preferences"
  r=$(send_test buyer "Looking for 3 bed 2 bath around \$400k in Rancho Cucamonga" "$BUYER_CID")
  resp=$(field "$r" "response"); turn=$(field "$r" "turn")
  [[ -n "$resp" ]] && pass "B-Q1: got response (turn $turn)" || fail "B-Q1: no response"
  assert_not_contains "B-Q1 no seller terms" "$resp" \
    "condition" "cash offer" "no repairs" "2-3 weeks"
  echo "    BOT: $resp" | head -c 200; echo
  sleep "$STEP_DELAY"

  # B-Q2
  echo ""
  blue "  [B-Q2] Pre-approval"
  r=$(send_test buyer "Yes I am pre-approved with my lender already" "$BUYER_CID")
  resp=$(field "$r" "response"); turn=$(field "$r" "turn")
  [[ -n "$resp" ]] && pass "B-Q2: got response (turn $turn)" || fail "B-Q2: no response"
  assert_not_contains "B-Q2 no seller terms" "$resp" \
    "condition" "cash offer" "no repairs" "2-3 weeks"
  echo "    BOT: $resp" | head -c 200; echo
  sleep "$STEP_DELAY"

  # B-Q3
  echo ""
  blue "  [B-Q3] Timeline"
  r=$(send_test buyer "We need to move within 30 days, pretty urgent situation" "$BUYER_CID")
  resp=$(field "$r" "response"); turn=$(field "$r" "turn")
  [[ -n "$resp" ]] && pass "B-Q3: got response (turn $turn)" || fail "B-Q3: no response"
  assert_not_contains "B-Q3 no seller terms" "$resp" \
    "condition" "cash offer" "no repairs" "2-3 weeks"
  echo "    BOT: $resp" | head -c 200; echo
  sleep "$STEP_DELAY"

  # B-Q4 — scheduling should appear
  echo ""
  blue "  [B-Q4] Motivation — scheduling offer expected"
  r=$(send_test buyer "Growing family, we need more space for the kids" "$BUYER_CID")
  resp=$(field "$r" "response"); turn=$(field "$r" "turn")
  [[ -n "$resp" ]] && pass "B-Q4: got response (turn $turn)" || fail "B-Q4: no response"
  assert_not_contains "B-Q4 no seller terms" "$resp" \
    "condition" "cash offer" "no repairs" "2-3 weeks"
  # Scheduling offer — should mention time/schedule/call/tour
  if echo "$resp" | grep -qiE "schedule|tour|call|morning|afternoon|evening|time.*work|book" 2>/dev/null; then
    pass "B-Q4: scheduling offer detected"
  else
    warn "B-Q4: no scheduling offer detected in response — check SMS manually"
  fi
  echo "    BOT: $resp" | head -c 300; echo
  sleep "$STEP_DELAY"

  # B-CAL
  echo ""
  blue "  [B-CAL] Calendar selection"
  r=$(send_test buyer "The first one works for me" "$BUYER_CID")
  resp=$(field "$r" "response"); turn=$(field "$r" "turn")
  [[ -n "$resp" ]] && pass "B-CAL: got response (turn $turn)" || fail "B-CAL: no response"
  echo "    BOT: $resp" | head -c 200; echo
  sleep "$STEP_DELAY"
}

# ─── Seller flow ──────────────────────────────────────────────────────────────
seller_flow() {
  bold ""
  bold "═══════════════════════════════════════"
  bold " SELLER BOT FLOW (automated)"
  bold "═══════════════════════════════════════"

  # The /test/seller endpoint keeps session in-process per contact_id.
  # If Render has multiple instances, requests can land on different ones and
  # lose state. We retry the full flow up to 3 times until turns are sequential.

  local MAX_RETRIES=3 attempt=0 success=false

  while [[ $attempt -lt $MAX_RETRIES && "$success" == "false" ]]; do
    attempt=$((attempt+1))
    SELLER_CID="e2e-seller-$(date +%s)-a${attempt}"
    echo "  Attempt $attempt/3 — Contact ID: $SELLER_CID"
    echo ""

    local r resp temp
    local t0 t1 t2 t3 t4 t5

    # Run all 6 steps fast with no delay to stay on same instance
    local r0 r1 r2 r3 r4 r5
    r0=$(send_test seller "I am thinking about selling my house actually" "$SELLER_CID" true)
    r1=$(send_test seller "It needs some minor fixes, nothing major though" "$SELLER_CID")
    r2=$(send_test seller "I think its worth around \$580k based on similar sales nearby" "$SELLER_CID")
    r3=$(send_test seller "Job relocation, I need to move for work as soon as possible" "$SELLER_CID")
    r4=$(send_test seller "Yes that timeline works for me, lets move forward" "$SELLER_CID")
    r5=$(send_test seller "The second option please" "$SELLER_CID")

    t0=$(field "$r0" "turn"); t1=$(field "$r1" "turn")
    t2=$(field "$r2" "turn"); t3=$(field "$r3" "turn")
    t4=$(field "$r4" "turn"); t5=$(field "$r5" "turn")

    # Check turns are monotonically increasing (session persisted)
    if python3 -c "
turns = [int(x) for x in '$t0 $t1 $t2 $t3 $t4 $t5'.split() if x.isdigit()]
ok = len(turns) == 6 and all(turns[i] < turns[i+1] for i in range(len(turns)-1))
exit(0 if ok else 1)
" 2>/dev/null; then
      success=true
      yellow "  Session consistent (turns: $t0 $t1 $t2 $t3 $t4 $t5)"
    else
      yellow "  Session inconsistent (turns: $t0 $t1 $t2 $t3 $t4 $t5) — retrying..."
      sleep 2
    fi
  done

  if [[ "$success" == "false" ]]; then
    warn "Could not get consistent seller session after $MAX_RETRIES attempts"
    warn "Results below may be from a fragmented session"
  fi

  echo ""

  # Now assert on the captured responses
  local resp0 resp1 resp2 resp3 resp4 resp5
  resp0=$(field "$r0" "response"); resp1=$(field "$r1" "response")
  resp2=$(field "$r2" "response"); resp3=$(field "$r3" "response")
  resp4=$(field "$r4" "response"); resp5=$(field "$r5" "response")

  # S-Q0 — CRITICAL: must ask CONDITION not address
  blue "  [S-Q0] Initial seller message — Q0 must ask CONDITION not address"
  [[ -n "$resp0" ]] && pass "S-Q0: got response (turn $t0)" || fail "S-Q0: no response"
  if echo "$resp0" | grep -qiE "address|street|property address|where.*located" 2>/dev/null; then
    fail "S-Q0 [BUG]: asks for property address instead of condition"
    warn "S-Q0: Bug present — Q0 should ask 'move-in ready / minor fixes / major repairs'"
  else
    pass "S-Q0: does NOT ask for address"
  fi
  if echo "$resp0" | grep -qiE "condition|move.in ready|minor fix|major repair|repairs|work needed" 2>/dev/null; then
    pass "S-Q0: asks about property condition"
  else
    warn "S-Q0: condition keywords not detected — verify manually"
  fi
  assert_not_contains "S-Q0 no buyer terms" "$resp0" \
    "pre.approv" "bedrooms to buy" "buying power" "scheduled tour"
  echo "    BOT: ${resp0:0:250}"; echo ""

  # S-Q1
  blue "  [S-Q1] Condition response (turn $t1)"
  [[ -n "$resp1" ]] && pass "S-Q1: got response" || fail "S-Q1: no response"
  assert_not_contains "S-Q1 no buyer terms" "$resp1" \
    "pre.approv" "bedrooms to buy" "buying power" "scheduled tour"
  echo "    BOT: ${resp1:0:200}"; echo ""

  # S-Q2
  blue "  [S-Q2] Property value (turn $t2)"
  [[ -n "$resp2" ]] && pass "S-Q2: got response" || fail "S-Q2: no response"
  assert_not_contains "S-Q2 no buyer terms" "$resp2" \
    "pre.approv" "bedrooms to buy" "buying power" "scheduled tour"
  echo "    BOT: ${resp2:0:200}"; echo ""

  # S-Q3 — CRITICAL P0: cash offer MUST appear
  blue "  [S-Q3] Motivation — CRITICAL: cash offer ~\$435K must appear (turn $t3)"
  local temp3; temp3=$(field "$r3" "temperature")
  [[ -n "$resp3" ]] && pass "S-Q3: got response (temp: $temp3)" || fail "S-Q3: no response"
  assert_cash_offer "S-Q3 [P0]" "$resp3"
  assert_not_contains "S-Q3 no buyer terms" "$resp3" \
    "pre.approv" "bedrooms to buy" "buying power" "scheduled tour"
  echo "    BOT: ${resp3:0:400}"; echo ""

  # S-Q4
  blue "  [S-Q4] Accepts offer — scheduling expected (turn $t4)"
  local temp4; temp4=$(field "$r4" "temperature")
  [[ -n "$resp4" ]] && pass "S-Q4: got response (temp: $temp4)" || fail "S-Q4: no response"
  if echo "$resp4" | grep -qiE "schedule|call|morning|afternoon|evening|time.*work|book|appointment" 2>/dev/null; then
    pass "S-Q4: scheduling offer detected"
  else
    warn "S-Q4: no scheduling keywords in response"
  fi
  assert_not_contains "S-Q4 no buyer terms" "$resp4" \
    "pre.approv" "bedrooms to buy" "buying power" "scheduled tour"
  echo "    BOT: ${resp4:0:300}"; echo ""

  # S-CAL
  blue "  [S-CAL] Calendar selection (turn $t5)"
  [[ -n "$resp5" ]] && pass "S-CAL: got response" || fail "S-CAL: no response"
  echo "    BOT: ${resp5:0:200}"; echo ""
}

# ─── Real SMS flow ────────────────────────────────────────────────────────────
sms_flow() {
  bold ""
  bold "═══════════════════════════════════════"
  bold " REAL SMS FLOW (phone: $PHONE)"
  bold "═══════════════════════════════════════"

  if [[ "$NO_SMS" == "true" ]]; then
    yellow "  Skipped (--no-sms flag)"
    return
  fi

  yellow ""
  yellow "  ⚠  PREREQUISITE: Remove 'Jorge-Active' tag from contact $CONTACT_ID in GHL"
  yellow "     Without this, the bot is silenced and no SMS will be sent."
  yellow "     Go to GHL → Contacts → $CONTACT_ID → Tags → Remove 'Jorge-Active'"
  yellow ""
  read -r -p "  Press ENTER to send buyer SMS (or Ctrl+C to abort): "

  echo ""
  blue "  [SMS-B-Q0] Buyer initial message → phone $PHONE"
  local result http_code body
  result=$(send_webhook "buyer" "Hi, I am interested in buying a home in the area")
  http_code="${result%%|*}"; body="${result#*|}"
  if [[ "$http_code" == "200" ]]; then
    pass "SMS-B-Q0: HTTP 200"
    local msg; msg=$(echo "$body" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('message','') or d.get('status',''))" 2>/dev/null || echo "$body")
    if echo "$msg" | grep -qi "deactivat" 2>/dev/null; then
      fail "SMS-B-Q0: Jorge-Active tag still set — remove it from GHL first"
    else
      pass "SMS-B-Q0: no deactivation — SMS should arrive"
    fi
  else
    fail "SMS-B-Q0: HTTP $http_code"
  fi
  sms_prompt "SMS-B-Q0" "Jorge greeting + asks about beds/baths/price/area"
  sleep "$SMS_DELAY"

  # Seller SMS
  echo ""
  blue "  [SMS-S-Q0] Bot switch to seller"
  result=$(send_webhook "seller" "Actually I am thinking about selling my house")
  http_code="${result%%|*}"; body="${result#*|}"
  [[ "$http_code" == "200" ]] && pass "SMS-S-Q0: HTTP 200" || fail "SMS-S-Q0: HTTP $http_code"
  sms_prompt "SMS-S-Q0" "Seller greeting + asks about CONDITION (not address)"
  sleep "$SMS_DELAY"
}

# ─── Summary ──────────────────────────────────────────────────────────────────
summary() {
  local total=$((PASS+FAIL+WARN))
  bold ""
  bold "═══════════════════════════════════════"
  bold " E2E TEST SUMMARY"
  bold "═══════════════════════════════════════"
  green "  PASS: $PASS"
  [[ $FAIL -gt 0 ]] && red "  FAIL: $FAIL" || echo "  FAIL: 0"
  [[ $WARN -gt 0 ]] && yellow "  WARN: $WARN" || echo "  WARN: 0"
  echo ""

  if [[ $FAIL -eq 0 ]]; then
    green "  VERDICT: PASS (all automated checks)"
  elif [[ $FAIL -le 3 ]]; then
    yellow "  VERDICT: CONDITIONAL — $FAIL check(s) failed (likely known bugs not yet deployed)"
  else
    red "  VERDICT: FAIL — $FAIL automated check(s) failed"
  fi

  bold ""
  bold "  Known live bugs (require deploy of local fixes):"
  yellow "  • S-Q0: Live server asks for property ADDRESS — fix asks for CONDITION"
  yellow "  • S-Q3: Live server may skip cash offer — fix gates on offer_presented"
  yellow ""
  bold "  To deploy fixes:"
  yellow "  The live service (service6_lead_recovery_engine v2.0.0) is a DIFFERENT"
  yellow "  codebase from this repo. To deploy:"
  yellow "  1. Identify which GitHub repo Render service srv-d6d5go15pdvs73fcjjq0 pulls from"
  yellow "  2. Apply the same S-Q0 + offer_presented fixes to that codebase"
  yellow "  3. Push to trigger Render redeploy"
  yellow ""
  bold "  Manual SMS checklist (after removing Jorge-Active tag):"
  yellow "  □ SMS-B-Q0: Jorge greeting + asks beds/baths/price/area"
  yellow "  □ SMS-S-Q0: Jorge greeting + asks about CONDITION (not address)"
  yellow "  □ S-Q3 SMS: ~\$435K cash offer + '2-3 weeks' + 'no repairs'"
  yellow "  □ No cross-contamination in any SMS"
}

# ─── Main ─────────────────────────────────────────────────────────────────────
main() {
  bold ""
  bold "╔════════════════════════════════════════╗"
  bold "║  Jorge GHL Bots — E2E Live Acceptance  ║"
  bold "║  Test endpoints: /test/seller /test/buyer║"
  bold "╚════════════════════════════════════════╝"
  echo ""
  echo "  URL:         $BASE_URL"
  echo "  SMS contact: $CONTACT_ID ($PHONE)"
  echo "  Buyer CID:   $BUYER_CID"
  echo "  Seller CID:  $SELLER_CID"
  echo ""

  preflight
  buyer_flow
  seller_flow
  sms_flow
  summary
}

main "$@"
