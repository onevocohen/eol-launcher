#!/usr/bin/env python3
"""
create_deck.py — Build a Idira EOL Google Slides deck from structured JSON.

Copies the shared EOL template, then populates each slide with real content.

Usage:
    python3 create_deck.py /tmp/eol_input.json

Input JSON fields:
    product_name           (str)  Name of the product being EOLed
    date                   (str)  Deck date, e.g. "Q2 2026"
    announcement           (str)  One-paragraph summary of what is being announced
    key_dates              (list) Important EOL milestone dates
    rationale              (list) Business/strategic reasons for EOL (bullet points)
    open_opportunities     (str)  Open pipeline / deals affected
    escalation             (str)  Escalation path for affected deals
    for_new_customers      (str)  Guidance for new customer requests
    for_existing_customers (str)  Guidance for renewals / existing contracts
    alternatives           (str)  Alternative solutions to offer
    pricing_impact         (str)  Pricing transition details
    communication          (str)  How / when Idira will communicate
    who_notified           (str)  Customer segments to notify
    contact                (str)  Point of contact for questions
    impacted_skus          (list) SKU codes / names affected
    status_notes           (str)  Optional: current status for the roadmap slide
    eol_type               (str)  "product" | "feature" — drives SKU / pricing logic
    commercial_impact      (bool) Feature only: sold or priced separately
    field_status           (dict) Optional {field: known|proposed|open}
    open_questions         (list) Optional extra kickoff discussion points

Missing or "TBD" fields don't block the deck: eol_rules.py fills smart
defaults (marked Proposed) or shows TBD and adds the item to the
"Open Questions & Decisions" slide.
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vault_http import google_api, ApiError  # noqa: E402
import eol_rules  # noqa: E402

TEMPLATE_ID   = "1jSiJII27Hr3guxSgDt_D-dFHNCRL3GaCm2J53gu0ZU0"
COPY_URL      = f"https://docs.google.com/presentation/d/{TEMPLATE_ID}/copy"
SLIDES_API    = "https://slides.googleapis.com/v1/presentations"
DRIVE_API     = "https://www.googleapis.com/drive/v3/files"
EOL_FOLDER_ID = "1xu1sh1ttQIrX3ztb-pQh9ZCfkxTLwrJt"  # EOL deck shared Drive folder


# ── HTTP helpers ──────────────────────────────────────────────────────────────
# Auth is handled by vault_http: GOOGLE_ACCESS_TOKEN if set, otherwise the
# sealed pm-claude-code-setup vault (token never enters this process).

def get_token():
    return None  # kept for call-site compatibility; vault_http resolves auth


def api(url, token=None, method="GET", body=None):
    try:
        return google_api(url, method, body)
    except ApiError as e:
        print(f"HTTP {e.status}: {e.body}", file=sys.stderr)
        raise


def copy_template(token, title):
    # supportsAllDrives=true is required when the template lives in a Shared Drive
    # parents places the new deck directly in the EOL shared folder
    return api(
        f"{DRIVE_API}/{TEMPLATE_ID}/copy?supportsAllDrives=true",
        token, "POST",
        {"name": title, "parents": [EOL_FOLDER_ID]},
    )


def get_presentation(token, pres_id):
    return api(f"{SLIDES_API}/{pres_id}", token)


def batch_update(token, pres_id, requests):
    return api(f"{SLIDES_API}/{pres_id}:batchUpdate", token, "POST",
               {"requests": requests})


# ── Content helpers ───────────────────────────────────────────────────────────

def bullets(items):
    """Convert a list to a bullet string, or return a plain string unchanged."""
    if isinstance(items, list):
        return "\n".join(f"• {item}" for item in items)
    return str(items or "")


def _element_text(el):
    """Return concatenated plain text of a page element."""
    return "".join(
        te.get("textRun", {}).get("content", "")
        for te in el.get("shape", {}).get("text", {}).get("textElements", [])
    ).strip()


def replace_body(slide, new_text, reqs, match_keyword=None):
    """
    Replace the BODY placeholder text in a slide.
    If match_keyword is given, only replace the BODY element whose text
    contains that keyword (for slides with multiple BODY elements).
    """
    for el in slide.get("pageElements", []):
        shape = el.get("shape", {})
        ph    = shape.get("placeholder", {})
        if ph.get("type") != "BODY":
            continue
        if match_keyword and match_keyword.lower() not in _element_text(el).lower():
            continue
        oid = el["objectId"]
        reqs.append({"deleteText": {"objectId": oid,
                                    "textRange": {"type": "ALL"}}})
        reqs.append({"insertText": {"objectId": oid,
                                    "insertionIndex": 0,
                                    "text": new_text}})
        return True   # replaced
    return False


# ── Build batchUpdate requests ────────────────────────────────────────────────

LEGEND = ("Legend: “(Proposed — confirm at kickoff)” = assumption or default, not a decision. "
          "“TBD” = not known yet, listed below.")

# Object IDs for the two kickoff slides added before Q&A. Fixed IDs make the
# step idempotent: a deck that already has them isn't changed again.
KICKOFF_SLIDES = [("eol_kickoff_open", "Open Questions & Decisions"),
                  ("eol_kickoff_next", "Stakeholders & Next Steps")]


def set_text(oid, text, reqs):
    reqs.append({"deleteText": {"objectId": oid, "textRange": {"type": "ALL"}}})
    reqs.append({"insertText": {"objectId": oid, "insertionIndex": 0, "text": text}})


def open_questions_text(d):
    qs = d.get("_open_questions") or []
    lines = [LEGEND, "", "Open questions & pending decisions:"]
    lines += [f"• {q}" for q in qs] or ["• None: all inputs were provided"]
    assumptions = d.get("_assumptions") or []
    if assumptions:
        lines += ["", "Proposed assumptions to confirm:"]
        lines += [f"• {a}" for a in assumptions]
    return "\n".join(lines)


def stakeholders_text(d):
    st = d.get("_stakeholders") or {}
    lines = ["Invited to the kickoff:"]
    lines += [f"• {p['name']}: {p['role']}" for p in st.get("invited", [])]
    lines += ["", "Suggested to involve (owners to confirm):"]
    lines += [f"• {s}" for s in st.get("suggested", [])]
    lines += ["", "Suggested next steps:"]
    lines += [f"• {s}" for s in d.get("_next_steps") or []]
    return "\n".join(lines)


def kickoff_font_pt(text):
    """The layout body is 24pt (about 14 lines); these slides are lists, so size
    the font to the line count instead of overflowing the text box."""
    lines = text.count("\n") + 1
    return 14 if lines <= 20 else 12 if lines <= 25 else 10


def add_kickoff_slides(slides, d, reqs):
    """Duplicate the slide 9 layout twice, right after slide 9, then fill
    title and body. Slide order becomes: … 9, Open Questions, Stakeholders, Q&A."""
    if len(slides) < 9 or any(s.get("objectId") == KICKOFF_SLIDES[0][0] for s in slides):
        return
    src = slides[8]
    title_id = body_id = None
    for el in src.get("pageElements", []):
        ph = el.get("shape", {}).get("placeholder", {}).get("type")
        if ph == "TITLE" and not title_id:
            title_id = el["objectId"]
        elif ph == "BODY" and not body_id:
            body_id = el["objectId"]
    if not (title_id and body_id):
        return
    texts = {"eol_kickoff_open": open_questions_text(d),
             "eol_kickoff_next": stakeholders_text(d)}
    # Each duplicate lands right after slide 9, so add them in reverse order.
    for sid, _ in reversed(KICKOFF_SLIDES):
        reqs.append({"duplicateObject": {"objectId": src["objectId"], "objectIds": {
            src["objectId"]: sid, title_id: sid + "_t", body_id: sid + "_b"}}})
    for sid, title in KICKOFF_SLIDES:
        set_text(sid + "_t", title, reqs)
        set_text(sid + "_b", texts[sid], reqs)
        reqs.append({"updateTextStyle": {
            "objectId": sid + "_b", "textRange": {"type": "ALL"},
            "style": {"fontSize": {"magnitude": kickoff_font_pt(texts[sid]), "unit": "PT"}},
            "fields": "fontSize"}})


def build_requests(slides, d):
    d = eol_rules.apply(d)
    r = lambda f: eol_rules.render(f, d)  # noqa: E731
    commercial = eol_rules.is_commercial(d)
    reqs = []

    # ── Slide 1: Cover ────────────────────────────────────────────────────────
    for el in slides[0].get("pageElements", []):
        ph = el.get("shape", {}).get("placeholder", {})
        if ph.get("type") == "SUBTITLE":
            set_text(el["objectId"], d.get("date", ""), reqs)
            break

    # ── Slide 2: EOL Roadmap ──────────────────────────────────────────────────
    status = str(d.get("status_notes", "")).strip()
    if status and len(slides) > 1:
        replace_body(slides[1], f"Status & Updates\n{status}", reqs, match_keyword="status")

    # ── Slide 3: Announcement & Timeline ─────────────────────────────────────
    if len(slides) > 2:
        replace_body(slides[2], f"{r('announcement')}\n\nKey Dates:\n{r('key_dates')}", reqs)

    # ── Slide 4: Business Rationale ───────────────────────────────────────────
    if len(slides) > 3:
        replace_body(slides[3], r("rationale"), reqs)

    # ── Slide 5: Customer Impact ──────────────────────────────────────────────
    if len(slides) > 4:
        heading = "Open Opportunities:" if commercial else "Affected Tenants / Usage:"
        replace_body(slides[4], f"{heading}\n{r('open_opportunities')}\n\n"
                                f"Escalation:\n{r('escalation')}", reqs)

    # ── Slide 6: Sales & Renewals Guidance ───────────────────────────────────
    if len(slides) > 5:
        replace_body(slides[5], f"For New Customers:\n{r('for_new_customers')}\n\n"
                                f"For Existing Customers:\n{r('for_existing_customers')}", reqs)

    # ── Slide 7: Alternatives & Pricing ──────────────────────────────────────
    if len(slides) > 6:
        replace_body(slides[6], f"Alternative Solutions:\n{r('alternatives')}\n\n"
                                f"Pricing Impact:\n{r('pricing_impact')}", reqs)

    # ── Slide 8: Communication Plan ───────────────────────────────────────────
    if len(slides) > 7:
        replace_body(slides[7], f"Communication Plan:\n{r('communication')}\n\n"
                                f"Who will be notified?\n{r('who_notified')}\n\n"
                                f"Contact for More Info:\n{r('contact')}", reqs)

    # ── Slide 9: Technical & SKU Details ─────────────────────────────────────
    if len(slides) > 8:
        replace_body(slides[8], f"Impacted SKUs:\n{r('impacted_skus')}", reqs)

    # ── Slides 10–11: kickoff open questions, stakeholders, next steps ───────
    add_kickoff_slides(slides, d, reqs)

    # Safety pass: replace any remaining "CyberArk" text in the deck with "Idira"
    reqs.append({
        "replaceAllText": {
            "replaceText": "Idira",
            "containsText": {"text": "CyberArk", "matchCase": True},
        }
    })

    return reqs


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    """
    Usage:
        python3 create_deck.py <input.json>                  # auto-copy + populate
        python3 create_deck.py <input.json> <presentation_id> # populate existing deck
    """
    if len(sys.argv) < 2:
        print("Usage: python3 create_deck.py <input.json> [presentation_id]",
              file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1]) as f:
        data = json.load(f)

    # If a presentation ID was given, skip the copy step
    pres_id = sys.argv[2] if len(sys.argv) > 2 else None

    print("🔑 Authenticating…")
    token = get_token()

    if not pres_id:
        print("📋 Copying template via Drive API…")
        try:
            product_name = data.get("product_name", "Product")
            deck_title   = f"{product_name} EOL — {data.get('date') or eol_rules.today_label()}"
            copy    = copy_template(token, deck_title)
            pres_id = copy["id"]
            print(f"   Created: {pres_id}")
        except Exception as e:
            # Signal to the caller that browser-based copy is needed
            print(f"AUTO_COPY_FAILED: {e}", file=sys.stderr)
            print(f"COPY_URL: {COPY_URL}", file=sys.stderr)
            sys.exit(4)

    print("📊 Fetching presentation structure…")
    pres   = get_presentation(token, pres_id)
    slides = pres.get("slides", [])

    print(f"✍️  Populating {len(slides)} slides…")
    reqs = build_requests(slides, data)
    if reqs:
        batch_update(token, pres_id, reqs)
    else:
        print("   (no replaceable content found — check slide structure)")

    url = f"https://docs.google.com/presentation/d/{pres_id}/edit"
    print(f"\n✅ EOL deck ready: {url}")
    return url


if __name__ == "__main__":
    main()
