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
"""

import json
import sys
import os
import urllib.request
import urllib.parse

TEMPLATE_ID   = "1jSiJII27Hr3guxSgDt_D-dFHNCRL3GaCm2J53gu0ZU0"
COPY_URL      = f"https://docs.google.com/presentation/d/{TEMPLATE_ID}/copy"
SLIDES_API    = "https://slides.googleapis.com/v1/presentations"
DRIVE_API     = "https://www.googleapis.com/drive/v3/files"
TOKEN_URL     = "https://oauth2.googleapis.com/token"
ADC_PATH      = os.path.expanduser("~/.config/gcloud/application_default_credentials.json")
QUOTA_PROJECT = "pntops"


# ── Auth ─────────────────────────────────────────────────────────────────────

def get_token():
    with open(ADC_PATH) as f:
        creds = json.load(f)
    data = urllib.parse.urlencode({
        "client_id":     creds["client_id"],
        "client_secret": creds["client_secret"],
        "refresh_token": creds["refresh_token"],
        "grant_type":    "refresh_token",
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=data, method="POST")
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)["access_token"]


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def api(url, token, method="GET", body=None):
    headers = {
        "Authorization":      f"Bearer {token}",
        "X-Goog-User-Project": QUOTA_PROJECT,
        "Content-Type":       "application/json",
    }
    data = json.dumps(body).encode() if body else None
    req  = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode()}", file=sys.stderr)
        raise


def copy_template(token, title):
    # supportsAllDrives=true is required when the template lives in a Shared Drive
    return api(f"{DRIVE_API}/{TEMPLATE_ID}/copy?supportsAllDrives=true",
               token, "POST", {"name": title})


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

def build_requests(slides, d):
    reqs = []

    # ── Slide 1: Cover ────────────────────────────────────────────────────────
    for el in slides[0].get("pageElements", []):
        ph = el.get("shape", {}).get("placeholder", {})
        if ph.get("type") == "SUBTITLE":
            oid = el["objectId"]
            reqs.append({"deleteText":  {"objectId": oid, "textRange": {"type": "ALL"}}})
            reqs.append({"insertText":  {"objectId": oid, "insertionIndex": 0,
                                         "text": d.get("date", "")}})
            break

    # ── Slide 2: EOL Roadmap ──────────────────────────────────────────────────
    # Update only the "Status & updates" BODY element if status_notes provided
    status = d.get("status_notes", "").strip()
    if status and len(slides) > 1:
        replace_body(slides[1],
                     f"Status & Updates\n{status}",
                     reqs,
                     match_keyword="status")

    # ── Slide 3: Announcement & Timeline ─────────────────────────────────────
    if len(slides) > 2:
        key_dates = bullets(d.get("key_dates", []))
        body = f"{d.get('announcement', '')}\n\nKey Dates:\n{key_dates}"
        replace_body(slides[2], body, reqs)

    # ── Slide 4: Business Rationale ───────────────────────────────────────────
    if len(slides) > 3:
        replace_body(slides[3], bullets(d.get("rationale", [])), reqs)

    # ── Slide 5: Customer Impact ──────────────────────────────────────────────
    if len(slides) > 4:
        body = (f"Open Opportunities:\n{d.get('open_opportunities', '')}\n\n"
                f"Escalation:\n{d.get('escalation', '')}")
        replace_body(slides[4], body, reqs)

    # ── Slide 6: Sales & Renewals Guidance ───────────────────────────────────
    if len(slides) > 5:
        body = (f"For New Customers:\n{d.get('for_new_customers', '')}\n\n"
                f"For Existing Customers:\n{d.get('for_existing_customers', '')}")
        replace_body(slides[5], body, reqs)

    # ── Slide 7: Alternatives & Pricing ──────────────────────────────────────
    if len(slides) > 6:
        body = (f"Alternative Solutions:\n{d.get('alternatives', '')}\n\n"
                f"Pricing Impact:\n{d.get('pricing_impact', '')}")
        replace_body(slides[6], body, reqs)

    # ── Slide 8: Communication Plan ───────────────────────────────────────────
    if len(slides) > 7:
        body = (f"How will Idira communicate?\n{d.get('communication', '')}\n\n"
                f"Who will be notified?\n{d.get('who_notified', '')}\n\n"
                f"Contact for More Info:\n{d.get('contact', '')}")
        replace_body(slides[7], body, reqs)

    # ── Slide 9: Technical & SKU Details ─────────────────────────────────────
    if len(slides) > 8:
        body = f"Impacted SKUs:\n{bullets(d.get('impacted_skus', []))}"
        replace_body(slides[8], body, reqs)

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
            deck_title   = f"{product_name} EOL — {data.get('date', '')}"
            copy    = copy_template(token, deck_title)
            pres_id = copy["id"]
            print(f"   Created: {pres_id}")
        except Exception as e:
            # Cross-org copy often fails with 404/403 — provide manual fallback
            print(f"\n⚠️  Auto-copy failed ({e}).")
            print(f"\nPlease copy the template manually:")
            print(f"   1. Open this URL in your browser: {COPY_URL}")
            print(f"   2. Google will create a copy in your Drive")
            print(f"   3. Copy the presentation ID from the new URL")
            print(f"      (the long string between /d/ and /edit)")
            print(f"   4. Re-run with the ID as the second argument:")
            print(f"      python3 create_deck.py {sys.argv[1]} <presentation_id>")
            sys.exit(1)

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
