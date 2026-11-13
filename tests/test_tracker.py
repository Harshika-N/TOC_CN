import os
import tempfile
import unittest

from tracker import create_app
from tracker.classification import classify, priority
from tracker.validation import validate_dfa, validate_regex, validate_identifier, route_key


class ValidationTests(unittest.TestCase):
    def test_valid_identifier(self): self.assertTrue(validate_identifier("BUS1234-ROUTEA01")["valid"])
    def test_lowercase_normalized(self): self.assertTrue(validate_identifier("bus1234-routea01")["valid"])
    def test_too_few_bus_digits(self): self.assertFalse(validate_identifier("BUS123-ROUTEA01")["valid"])
    def test_too_many_bus_digits(self): self.assertFalse(validate_identifier("BUS12345-ROUTEA01")["valid"])
    def test_missing_separator(self): self.assertFalse(validate_identifier("BUS1234ROUTEA01")["valid"])
    def test_multi_letter_route_rejected(self): self.assertFalse(validate_identifier("BUS1234-ROUTEAB01")["valid"])
    def test_suffix_requires_two_digits(self): self.assertFalse(validate_identifier("BUS1234-ROUTEA1")["valid"])
    def test_suffix_rejects_trailing_text(self): self.assertFalse(validate_identifier("BUS1234-ROUTEA01X")["valid"])
    def test_ascii_digits_only(self): self.assertFalse(validate_identifier("BUS１２３４-ROUTEA01")["valid"])
    def test_regex_and_dfa_agree(self):
        samples=["BUS1234-ROUTEA01","BUS0000-ROUTEH99","BUS123-ROUTEA01","BUS1234-ROUTE_01","","BUS1234-ROUTEA01x"]
        self.assertTrue(all(validate_dfa(x)==validate_regex(x) for x in samples))
    def test_route_key_extraction(self): self.assertEqual(route_key("BUS1234-ROUTEG18"),"G")
    def test_invalid_route_key_rejected(self):
        with self.assertRaises(ValueError): route_key("BUS1234-ROUTEG1")


class ClassificationTests(unittest.TestCase):
    def test_classifies_mechanical(self): self.assertEqual(classify("engine overheating"),"Mechanical")
    def test_classifies_tyre(self): self.assertEqual(classify("rear tyre puncture"),"Tyre")
    def test_classifies_accident(self): self.assertEqual(classify("collision at junction"),"Accident")
    def test_classifies_fuel(self): self.assertEqual(classify("fuel leak reported"),"Fuel")
    def test_classifies_electrical(self): self.assertEqual(classify("battery wiring fault"),"Electrical")
    def test_code_can_classify(self): self.assertEqual(classify("", "TYRE-PUNCTURE"),"Tyre")
    def test_accident_precedes_electrical_conflict(self): self.assertEqual(classify("accident with battery damage"),"Accident")
    def test_unmapped_description_is_not_guessed(self): self.assertIsNone(classify("noise"))
    def test_critical_urgency_overrides_priority(self): self.assertEqual(priority("Fuel","critical"),"Critical")


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.app=create_app({"TESTING":True,"DATABASE":os.path.join(self.temp.name,"test.db")})
        self.client=self.app.test_client()

    def tearDown(self): self.temp.cleanup()

    def payload(self, **overrides):
        value={"reporter":"Test Reporter","contact":"555-0100","bus_id":"BUS1234-ROUTEA01","code":"TYRE-PUNCTURE","description":"rear tyre puncture","urgency":"normal"}
        value.update(overrides); return value

    def post(self, **overrides): return self.client.post("/api/reports",json=self.payload(**overrides))

    def test_malformed_identifier_rejected_before_storage(self):
        self.assertEqual(self.post(bus_id="BUS123-ROUTEA01").status_code,400)
        self.assertEqual(self.client.get("/api/reports").json,[])

    def test_unknown_route_uses_correction_queue(self):
        r=self.post(bus_id="BUS1234-ROUTEZ01").json
        self.assertEqual(r["status"],"Queued")
        self.assertIn("central correction",r["routing_note"])

    def test_nearest_eligible_depot_selected(self):
        r=self.post().json
        self.assertEqual(r["depot_name"],"Central Depot")
        self.assertEqual(r["status"],"Assigned")

    def test_critical_report_escalates(self):
        r=self.post(urgency="critical").json
        self.assertEqual(r["status"],"Escalated")
        self.assertEqual(r["priority"],"Critical")

    def test_no_classification_rejected(self): self.assertEqual(self.post(description="unusual sound",code="OTHER").status_code,422)

    def test_invalid_status_transition_rejected(self):
        r=self.post().json
        self.assertEqual(self.client.patch(f"/api/reports/{r['id']}/status",json={"status":"Pending"}).status_code,400)

    def test_assigned_report_can_progress_and_resolve(self):
        r=self.post().json
        a=self.client.patch(f"/api/reports/{r['id']}/status",json={"status":"In Progress"})
        b=self.client.patch(f"/api/reports/{r['id']}/status",json={"status":"Resolved"})
        self.assertEqual((a.status_code,b.status_code),(200,200))

    def test_assignment_is_not_duplicated(self):
        r=self.post().json
        self.client.patch(f"/api/reports/{r['id']}/status",json={"status":"In Progress"})
        self.assertEqual(sum(x["id"]==r["id"] for x in self.client.get("/api/reports").json),1)

    def test_off_duty_handler_is_skipped(self):
        self.client.patch("/api/handlers/H-101",json={"available":False})
        self.assertNotEqual(self.post().json.get("handler_id"),"H-101")

    def test_capacity_overflow_uses_next_depot(self):
        for _ in range(4): self.post()
        self.assertEqual(self.post().json["depot_name"],"North Depot")

    def test_queues_and_escalations_visible(self):
        self.post(bus_id="BUS1234-ROUTEZ01"); self.post(urgency="critical")
        self.assertEqual(len(self.client.get("/api/routing").json["queue"]),2)

    def test_handler_capacity_updates(self):
        self.client.patch("/api/handlers/H-101",json={"capacity":4})
        row=next(x for x in self.client.get("/api/handlers").json if x["id"]=="H-101")
        self.assertEqual(row["capacity"],4)

    def test_unknown_handler_rejected(self):
        r=self.post().json
        self.assertEqual(self.client.patch(f"/api/reports/{r['id']}/status",json={"status":"Assigned","handler_id":"H-999"}).status_code,400)

    def test_analytics_counts_reports(self):
        self.post(); data=self.client.get("/api/analytics").json
        self.assertEqual(data["unresolved"],1)
        self.assertEqual(data["categories"][0]["category"],"Tyre")

    def test_submission_requires_contact_fields(self): self.assertEqual(self.post(contact="").status_code,400)


if __name__=="__main__": unittest.main()
