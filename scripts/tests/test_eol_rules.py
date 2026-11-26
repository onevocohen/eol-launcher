import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import eol_rules  # noqa: E402
import create_deck  # noqa: E402
import submit_asana  # noqa: E402

AMIR = eol_rules.AMIR["email"]
TODAY = date(2026, 11, 26)

# Minimal intake: name + type only (PM knows almost nothing yet).
PRODUCT_MIN = {"product_name": "Legacy Vault Appliance", "eol_type": "product",
               "pm_name": "Dana PM", "contact": "dana@example.com"}
FEATURE_MIN = {"product_name": "Classic Reports Export", "eol_type": "feature",
               "pm_name": "Dana PM", "contact": "dana@example.com"}


def fake_slides():
    """Template shape: 11 slides, slide 9 has a TITLE and a BODY."""
    def slide(i, phs):
        return {"objectId": f"s{i}", "pageElements": [
            {"objectId": f"s{i}_{p}", "shape": {"placeholder": {"type": p},
                                               "text": {"textElements": [
                                                   {"textRun": {"content": "Status & updates" if i == 2 else ""}}]}}}
            for p in phs]}
    slides = [slide(1, ["SUBTITLE"]), slide(2, ["BODY"])]
    slides += [slide(i, ["TITLE", "BODY"]) for i in range(3, 11)]
    slides.append(slide(11, []))
    return slides


class UnknownAnswers(unittest.TestCase):
    def test_unknown_markers(self):
        for v in ["", None, "TBD", "tbd.", "Don't know yet", "don’t know", "To be discussed during kickoff",
                  "TBD - need R&D input", "Not sure", "?", [], ["TBD"], "pending"]:
            self.assertTrue(eol_rules.is_unknown(v), v)

    def test_real_answers(self):
        for v in ["Q2 2027", "Pending Legal review, target Q2 2027", ["PAM-ENT-1"],
                  "No alternative", "Unknown-device support is replaced by X", False]:
            self.assertFalse(eol_rules.is_unknown(v), v)


class ProductVsFeature(unittest.TestCase):
    def test_product_is_commercial_and_invites_amir(self):
        d = eol_rules.apply(PRODUCT_MIN, TODAY)
        self.assertTrue(eol_rules.is_commercial(d))
        self.assertIn(AMIR, eol_rules.invite_emails(d))
        self.assertEqual(d["_status"]["impacted_skus"], "open")
        self.assertEqual(d["_status"]["pricing_impact"], "open")
        self.assertTrue(any("SKU" in q for q in d["_open_questions"]))
        self.assertTrue(any("RevOps" in s for s in d["_stakeholders"]["suggested"]))

    def test_plain_feature_skips_sku_pricing_and_amir(self):
        d = eol_rules.apply(FEATURE_MIN, TODAY)
        self.assertFalse(eol_rules.is_commercial(d))
        self.assertNotIn(AMIR, eol_rules.invite_emails(d))
        self.assertEqual(d["_status"]["pricing_impact"], "proposed")
        self.assertEqual(d["_status"]["impacted_skus"], "proposed")
        joined = " ".join(d["_open_questions"] + d["_next_steps"])
        self.assertNotIn("SKU", joined)
        self.assertNotIn("Amir", joined)
        self.assertNotIn("pricing", joined.lower())

    def test_feature_with_commercial_impact_brings_amir_back(self):
        d = eol_rules.apply(dict(FEATURE_MIN, commercial_impact=True), TODAY)
        self.assertTrue(eol_rules.is_commercial(d))
        self.assertIn(AMIR, eol_rules.invite_emails(d))
        self.assertEqual(d["_status"]["impacted_skus"], "open")

    def test_feature_with_real_skus_is_commercial(self):
        d = eol_rules.apply(dict(FEATURE_MIN, impacted_skus=["ADDON-REPORTS"]), TODAY)
        self.assertTrue(eol_rules.is_commercial(d))

    def test_missing_type_defaults_to_product_and_asks(self):
        d = eol_rules.apply({"product_name": "X"}, TODAY)
        self.assertEqual(eol_rules.eol_type(d), "product")
        self.assertTrue(any("product EOL or a feature EOL" in q for q in d["_open_questions"]))


class IncompleteInformation(unittest.TestCase):
    def test_tbd_answers_become_open_questions_not_facts(self):
        d = eol_rules.apply(dict(PRODUCT_MIN, key_dates="TBD", rationale="Don't know yet",
                                 alternatives="To be discussed during kickoff"), TODAY)
        for f in ("key_dates", "rationale", "alternatives"):
            self.assertEqual(d["_status"][f], "open")
            self.assertEqual(eol_rules.render(f, d), eol_rules.TBD_TEXT)

    def test_known_answers_are_kept_verbatim(self):
        d = eol_rules.apply(dict(PRODUCT_MIN, key_dates=["End of sale: Q2 2027"]), TODAY)
        self.assertEqual(d["_status"]["key_dates"], "known")
        self.assertEqual(eol_rules.render("key_dates", d), "• End of sale: Q2 2027")

    def test_defaults_are_marked_proposed(self):
        d = eol_rules.apply(FEATURE_MIN, TODAY)
        self.assertIn(eol_rules.PROPOSED_SUFFIX, eol_rules.render("communication", d))
        self.assertTrue(d["_assumptions"])

    def test_escalation_and_date_inferred(self):
        d = eol_rules.apply(PRODUCT_MIN, TODAY)
        self.assertEqual(d["date"], "November 2026")
        self.assertEqual(d["_status"]["escalation"], "known")
        self.assertIn("Dana PM", d["escalation"])

    def test_pm_marked_open_overrides_value(self):
        d = eol_rules.apply(dict(PRODUCT_MIN, alternatives="Maybe Vault SaaS",
                                 field_status={"alternatives": "open"}), TODAY)
        self.assertEqual(d["_status"]["alternatives"], "open")

    def test_no_alternative_adds_mitigation_question(self):
        d = eol_rules.apply(dict(PRODUCT_MIN, alternatives="No alternative"), TODAY)
        self.assertTrue(any("mitigation" in q for q in d["_open_questions"]))

    def test_apply_is_idempotent(self):
        once = eol_rules.apply(PRODUCT_MIN, TODAY)
        twice = eol_rules.apply(once, TODAY)
        self.assertEqual(once["_status"], twice["_status"])
        self.assertEqual(once["_open_questions"], twice["_open_questions"])


class Stakeholders(unittest.TestCase):
    def test_pm_who_is_also_a_reviewer_listed_once(self):
        d = eol_rules.apply(dict(PRODUCT_MIN, pm_name="Orit Nevo Cohen",
                                 contact=eol_rules.ORIT["email"]), TODAY)
        names = [p["name"] for p in d["_stakeholders"]["invited"]]
        self.assertEqual(names.count("Orit Nevo Cohen"), 1)

    def test_known_alternative_gives_proposed_existing_customer_path(self):
        d = eol_rules.apply(dict(FEATURE_MIN, alternatives="Reports API"), TODAY)
        self.assertEqual(d["_status"]["for_existing_customers"], "proposed")
        self.assertIn("Reports API", d["for_existing_customers"])


class DeckRequests(unittest.TestCase):
    def _texts(self, d):
        reqs = create_deck.build_requests(fake_slides(), d)
        return reqs, "\n".join(r["insertText"]["text"] for r in reqs if "insertText" in r)

    def test_minimal_product_builds_full_deck(self):
        reqs, text = self._texts(PRODUCT_MIN)
        self.assertEqual(sum(1 for r in reqs if "duplicateObject" in r), 2)
        self.assertIn("Open Questions & Decisions", text)
        self.assertIn("Stakeholders & Next Steps", text)
        self.assertIn("Amir Aviad", text)
        self.assertIn(eol_rules.TBD_TEXT, text)
        self.assertIn("Open Opportunities:", text)

    def test_minimal_feature_deck_has_no_amir_or_sku_question(self):
        _, text = self._texts(FEATURE_MIN)
        self.assertNotIn("Amir Aviad", text)
        self.assertNotIn("Which SKU codes", text)
        self.assertIn("Affected Tenants / Usage:", text)

    def test_kickoff_slides_not_added_twice(self):
        slides = fake_slides()
        slides.insert(9, {"objectId": "eol_kickoff_open", "pageElements": []})
        reqs = create_deck.build_requests(slides, PRODUCT_MIN)
        self.assertFalse(any("duplicateObject" in r for r in reqs))


class AsanaRecord(unittest.TestCase):
    def test_tbd_alternative_not_recorded_as_full(self):
        d = eol_rules.apply(dict(PRODUCT_MIN, alternatives="TBD"), TODAY)
        self.assertIsNone(submit_asana.map_alternative(d))

    def test_product_with_unknown_skus_records_sku_yes(self):
        d = eol_rules.apply(PRODUCT_MIN, TODAY)
        self.assertEqual(submit_asana.map_sku(d), submit_asana.SKU_YES)

    def test_plain_feature_records_sku_no(self):
        d = eol_rules.apply(FEATURE_MIN, TODAY)
        self.assertEqual(submit_asana.map_sku(d), submit_asana.SKU_NO)

    def test_notes_separate_open_questions(self):
        d = eol_rules.apply(PRODUCT_MIN, TODAY)
        notes = submit_asana.build_notes(d, "Dana PM", "dana@example.com")
        self.assertIn("Open questions for the EOL kickoff:", notes)
        self.assertNotIn("Key Dates:", notes)  # unknown -> not written as a fact


if __name__ == "__main__":
    unittest.main()
