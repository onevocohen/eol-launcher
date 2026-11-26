#!/usr/bin/env python3
"""
eol_rules.py — Conditional logic and smart defaults for the EOL kickoff.

The PM usually runs the EOL Kickoff Toolkit early, before most decisions are
made. This module turns whatever the PM knows into a complete kickoff package
without inventing answers:

  * known     — the PM said it, or it came from the Asana request form
  * proposed  — a default or inference; shown in the deck as "Proposed"
  * open      — not known yet; shown as TBD and listed as a kickoff question

It also decides, from the EOL type (product or feature), which SKU and pricing
items and which stakeholders apply. Every script imports it, so the deck, the
Asana task, the calendar invite and the Slack channel agree with each other.

Input JSON keys this module reads, on top of the deck fields:
    eol_type           "product" | "feature"   (missing -> treated as product)
    commercial_impact  bool  feature only: true when the feature is sold,
                             licensed or priced separately (SKU, add-on, ...)
    field_status       {field: "known" | "proposed" | "open"}  optional
    open_questions     [str]  extra items the PM wants discussed at kickoff
"""

from datetime import date

# Deck fields this module manages, in deck order.
FIELDS = [
    "announcement", "key_dates", "rationale", "open_opportunities",
    "escalation", "for_new_customers", "for_existing_customers",
    "alternatives", "pricing_impact", "communication", "who_notified",
    "contact", "impacted_skus",
]

KNOWN, PROPOSED, OPEN = "known", "proposed", "open"

TBD_TEXT = "TBD — open question for kickoff"
PROPOSED_SUFFIX = "(Proposed — confirm at kickoff)"

# Answers that mean "not decided yet". Compared after lower-casing and
# stripping punctuation, and also matched as a prefix ("TBD - need R&D input").
_UNKNOWN_MARKERS = (
    "tbd", "tba", "unknown yet", "still unknown", "not sure", "unsure", "don't know", "dont know",
    "do not know", "don't know yet", "not decided", "undecided",
    "to be discussed", "to be decided", "to be determined", "discuss at kickoff",
    "to be discussed during kickoff", "to be discussed at kickoff",
)
# Only unknown when they are the whole answer ("Pending Legal review, Q2" is real).
_UNKNOWN_EXACT = ("pending", "unknown", "?", "??", "n/a", "na", "-")

# Fixed review stakeholders (invited automatically).
YAEL = {"name": "Yael Gershon", "email": "ygershongob@paloaltonetworks.com",
        "role": "EOL review"}
ORIT = {"name": "Orit Nevo Cohen", "email": "onevocohen@paloaltonetworks.com",
        "role": "Product Operations"}
AMIR = {"name": "Amir Aviad", "email": "aaviad@paloaltonetworks.com",
        "role": "Pricing & SKUs"}


# ── Basic checks ──────────────────────────────────────────────────────────────

def is_unknown(value):
    """True when a value is empty or says the answer isn't known yet."""
    if value is None:
        return True
    if isinstance(value, (list, tuple)):
        return all(is_unknown(v) for v in value)
    if isinstance(value, bool):
        return False
    text = str(value).strip().lower().replace("’", "'")
    if not text:
        return True
    if text.strip(" .!") in _UNKNOWN_EXACT:
        return True
    text = text.strip(" .!—–-:")
    if not text:
        return True
    # "TBD - need R&D input" / "TBD, ask Sales" count; "Unknown-device ..." doesn't.
    return any(text == m or text.startswith(tuple(m + sep for sep in (" ", ",", ":", "(", " -", " —")))
               or (m in ("tbd", "tba") and text.startswith(m + "-"))
               for m in _UNKNOWN_MARKERS)


def eol_type(d):
    """'product' or 'feature'. Missing or unclear -> 'product' (stricter path)."""
    t = str(d.get("eol_type") or "").strip().lower()
    return "feature" if t.startswith("feature") else "product"


def type_confirmed(d):
    return str(d.get("eol_type") or "").strip().lower().startswith(("product", "feature"))


def meaningful_skus(d):
    skus = d.get("impacted_skus") or []
    if isinstance(skus, str):
        skus = [skus]
    return [s for s in skus if not is_unknown(s)
            and not str(s).strip().lower().startswith(("none", "n/a", "no sku"))]


def no_alternative(value):
    """True when the PM said there is no replacement."""
    text = str(value or "").strip().lower()
    return (text.startswith(("none", "no ")) or "no alternative" in text
            or "no replacement" in text or "no direct" in text)


def is_commercial(d):
    """SKU, pricing and Amir apply: every product EOL, and a feature EOL only
    when there's a sign of commercial impact (flag set, or real SKU codes)."""
    if eol_type(d) == "product":
        return True
    return bool(d.get("commercial_impact")) or bool(meaningful_skus(d))


def today_label(today=None):
    t = today or date.today()
    return t.strftime("%B %Y")


# ── Defaults and open questions ───────────────────────────────────────────────

def _open_question(field, d):
    """The kickoff question for a field nobody could answer yet."""
    product = eol_type(d) == "product"
    commercial = is_commercial(d)
    q = {
        "announcement": "Confirm the scope: exactly what is being retired?",
        "key_dates": ("Target dates: end of sale (stop selling), end of support and EOL?"
                      if product else
                      "In which release or by what date will the feature be removed?"),
        "rationale": "What is the business rationale for this EOL?",
        "open_opportunities": (
            "How many active customers, open opportunities and ARR are affected? (pull from Salesforce)"
            if commercial else
            "How many tenants actively use this feature? (pull from usage data)"),
        "escalation": "Who owns escalations for affected customers or deals?",
        "for_new_customers": "What should sales tell new prospects, and from when do we stop selling?",
        "for_existing_customers": (
            "What transition path do existing customers get (migration, bridge offer, extended support)?"
            if commercial else
            "What should current users of the feature do instead (migration steps or workaround)?"),
        "alternatives": "Is there a replacement (full, partial or none)? If so, which one?",
        "pricing_impact": "Any pricing changes, migration discounts or bridge offers? (Amir)",
        "communication": "How and when do we notify customers, and how much notice do they get?",
        "who_notified": "Which customer segments must be notified?",
        "contact": "Who is the field contact for EOL questions?",
        "impacted_skus": "Which SKU codes are retired? (confirm with Amir / RevOps)",
    }
    return q[field]


def _default(field, d):
    """(value, status) used when the field has no answer, or None to leave it open."""
    product = eol_type(d) == "product"
    commercial = is_commercial(d)
    name = d.get("product_name") or "this " + eol_type(d)
    pm_name = (d.get("pm_name") or "").strip()
    contact = (d.get("contact") or "").strip()
    alt = d.get("alternatives")
    alt_known = not is_unknown(alt) and not no_alternative(alt)

    if field == "announcement":
        kind = "product" if product else "feature"
        return (f"Idira plans to retire the {name} {kind}. "
                "Scope, dates and customer guidance will be finalized at the EOL kickoff.",
                PROPOSED)
    if field == "escalation" and pm_name:
        who = f"{pm_name} ({contact})" if contact and "@" in contact else pm_name
        return (f"{who}, the PM who owns this EOL", KNOWN)
    if field == "for_new_customers":
        if not commercial:
            return ("No sales action needed: the feature is not sold separately.", PROPOSED)
        if alt_known:
            return (f"Stop positioning {name} in new deals; lead with the alternative ({alt}).", PROPOSED)
        return None
    if field == "for_existing_customers" and alt_known:
        if commercial:
            return (f"Offer a migration path to {alt}; transition terms (bridge offer, "
                    "support window) to be agreed at kickoff.", PROPOSED)
        return (f"Move to {alt}; migration guidance and documentation to be prepared.", PROPOSED)
    if field == "pricing_impact" and not commercial:
        return ("No pricing impact: feature deprecation with no associated SKU.", PROPOSED)
    if field == "impacted_skus" and not commercial:
        return (["None: feature deprecation with no associated SKU"], PROPOSED)
    if field == "communication":
        if commercial:
            return ("Customer email and in-app notification through the External Communication "
                    "Request process (final content and Legal approval required), plus "
                    "account-team / CSM outreach to affected customers.", PROPOSED)
        return ("Release notes / What's New entry and a documentation update, plus an in-app "
                "notification for active users. A dedicated customer announcement only if "
                "the impact is significant (External Communication Request).", PROPOSED)
    if field == "who_notified":
        if commercial:
            return ("Customers and partners with active entitlements on the impacted SKUs, "
                    "plus prospects in open pipeline.", PROPOSED)
        return ("Tenants that actively use the feature.", PROPOSED)
    return None


def _extra_questions(d, status):
    """Questions that follow from process logic, not from a single empty field."""
    qs = []
    if not type_confirmed(d):
        qs.append("Is this a product EOL or a feature EOL? (deck assumes product)")
    if status.get("alternatives") == KNOWN and no_alternative(d.get("alternatives")):
        qs.append("No replacement: what mitigation do we offer affected customers?")
    if status.get("communication") != KNOWN and status.get("key_dates") == KNOWN:
        qs.append("Customer notice period: how far ahead of the EOL date do we announce?")
    return qs


# ── Main entry point ──────────────────────────────────────────────────────────

def apply(d, today=None):
    """Return a copy of d with every deck field filled and these keys added:
        _status          {field: known|proposed|open}
        _open_questions  [str]   kickoff questions and pending decisions
        _assumptions     [str]   proposed items to confirm
        _stakeholders    {"invited": [...], "suggested": [...]}
        _next_steps      [str]
    Calling it twice is safe."""
    out = dict(d)
    # A previous apply() result keeps its statuses, so calling twice is safe.
    given_status = d.get("_status") or d.get("field_status") or {}
    status = {}

    if is_unknown(out.get("date")):
        out["date"] = today_label(today)
    if is_unknown(out.get("status_notes")):
        out["status_notes"] = "Kickoff: EOL plan in preparation"

    questions = []
    for field in FIELDS:
        value = out.get(field)
        if not is_unknown(value) and given_status.get(field) != OPEN:
            st = given_status.get(field)
            status[field] = st if st in (KNOWN, PROPOSED) else KNOWN
            continue
        default = _default(field, out)
        if default:
            out[field], status[field] = default
        else:
            out[field] = [] if field in ("key_dates", "rationale", "impacted_skus") else ""
            status[field] = OPEN
            questions.append(_open_question(field, out))

    questions += _extra_questions(out, status)
    for q in d.get("open_questions") or []:
        if str(q).strip() and q not in questions:
            questions.append(str(q).strip())

    out["_status"] = status
    out["_open_questions"] = questions
    out["_assumptions"] = [f"{label(f)}: {_short(out[f])}" for f in FIELDS
                           if status[f] == PROPOSED]
    out["_stakeholders"] = stakeholders(out)
    out["_next_steps"] = next_steps(out)
    return out


_LABELS = {
    "announcement": "Announcement", "key_dates": "Key dates", "rationale": "Rationale",
    "open_opportunities": "Customer impact", "escalation": "Escalation",
    "for_new_customers": "New customers", "for_existing_customers": "Existing customers",
    "alternatives": "Alternative", "pricing_impact": "Pricing impact",
    "communication": "Communication", "who_notified": "Who is notified",
    "contact": "Contact", "impacted_skus": "Impacted SKUs",
}


def label(field):
    return _LABELS.get(field, field)


def _short(value, limit=110):
    text = "; ".join(map(str, value)) if isinstance(value, list) else str(value)
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


# ── Rendering ─────────────────────────────────────────────────────────────────

def bullets(items):
    if isinstance(items, list):
        return "\n".join(f"• {item}" for item in items)
    return str(items or "")


def render(field, d):
    """Deck text for one field, tagged with its status."""
    st = (d.get("_status") or {}).get(field, KNOWN)
    value = d.get(field)
    if st == OPEN or is_unknown(value):
        return TBD_TEXT
    text = bullets(value) if isinstance(value, list) else str(value)
    if st == PROPOSED:
        return f"{text}\n{PROPOSED_SUFFIX}" if isinstance(value, list) else f"{text} {PROPOSED_SUFFIX}"
    return text


# ── Stakeholders ──────────────────────────────────────────────────────────────

def stakeholders(d):
    """Who is invited automatically, and which roles to bring in (by role,
    not by name, since owners differ per product line)."""
    pm_name = (d.get("pm_name") or "").strip()
    pm_email = (d.get("contact") or "").strip().lower()
    people = []
    if pm_name or pm_email:
        people.append({"name": pm_name or pm_email, "email": pm_email, "role": "PM, EOL owner"})
    people += [YAEL, ORIT] + ([AMIR] if is_commercial(d) else [])
    people += [{"name": e, "email": e.strip().lower(), "role": "Added by PM"}
               for e in d.get("slack_additional_members") or []]
    # One line per person: the PM may also be a fixed reviewer (e.g. Orit).
    invited, seen = [], {}
    for p in people:
        key = p.get("email") or p["name"]
        if key in seen:
            first = seen[key]
            if p["role"] not in first["role"]:
                first["role"] += f", {p['role']}"
            continue
        seen[key] = dict(p)
        invited.append(seen[key])

    commercial = is_commercial(d)
    if eol_type(d) == "product":
        suggested = [
            "R&D lead: technical sunset plan and support window",
            "RevOps / Order Management: SKU retirement and price list",
            "Sales leadership / Deal Desk: pipeline and renewal handling",
            "Customer Success: affected accounts and migration",
            "Support: support policy until EOL",
            "Marketing / Customer Communications: announcement",
            "Legal: contractual notice obligations",
            "Technical Writers: documentation and EOL notice",
        ]
    else:
        suggested = [
            "R&D lead: removal release and technical impact",
            "Support: expected questions and workaround",
            "Technical Writers: documentation and What's New",
            "Customer Success: only if strategic accounts use the feature",
        ]
        if commercial:
            suggested.insert(1, "RevOps / Order Management: SKU or add-on retirement")
            suggested.insert(2, "Sales / Deal Desk: affected deals and renewals")
    return {"invited": invited, "suggested": suggested}


def invite_emails(d):
    """Fixed reviewer emails for the calendar invite and Slack channel."""
    emails = [YAEL["email"], ORIT["email"]]
    if is_commercial(d):
        emails.append(AMIR["email"])
    return emails


# ── Next steps ────────────────────────────────────────────────────────────────

def next_steps(d):
    status = d.get("_status") or {}
    n_open = len(d.get("_open_questions") or [])
    steps = []
    if n_open:
        steps.append(f"Resolve the {n_open} open questions on the previous slide and assign owners")
    if status.get("key_dates") != KNOWN:
        steps.append("Confirm the EOL timeline")
    if is_commercial(d):
        if status.get("impacted_skus") != KNOWN:
            steps.append("Confirm the impacted SKU list with Amir and RevOps")
        steps.append("Pull affected customers, open opportunities and ARR")
        if status.get("pricing_impact") != KNOWN or status.get("for_existing_customers") != KNOWN:
            steps.append("Define the migration / bridge offer for existing customers")
        steps.append("Submit the customer announcement through the External Communication "
                     "Request (Legal approval required)")
    else:
        steps.append("Pull feature usage data to size the impact")
        steps.append("Plan the What's New entry and documentation update with the Technical Writers")
    steps.append("Update the Asana EOL request and this deck after the kickoff")
    return steps


# ── CLI: summary for the PM readout (Step 7) ─────────────────────────────────

def summary(d):
    d = apply(d)
    st = d["_status"]
    return {
        "eol_type": eol_type(d) if type_confirmed(d) else "type TBD, treated as product",
        "commercial": is_commercial(d),
        "known": [label(f) for f in FIELDS if st[f] == KNOWN],
        "proposed": d["_assumptions"],
        "open_questions": d["_open_questions"],
        "invited": [p["name"] for p in d["_stakeholders"]["invited"]],
    }


if __name__ == "__main__":
    import json
    import sys
    if len(sys.argv) != 3 or sys.argv[1] != "summary":
        print("Usage: python3 eol_rules.py summary <eol_input.json>", file=sys.stderr)
        sys.exit(1)
    with open(sys.argv[2]) as f:
        print(json.dumps(summary(json.load(f)), indent=1, ensure_ascii=False))
