import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scoring import score_lead, WEIGHTS

SAMPLE = dict(name="Rahul Sharma", company="ABC Technologies", website="www.abctechnologies.com",
              job_title="Founder", industry="IT Services", location="Bangalore", company_size="50-100 Employees",
              lead_source="Website", requirement="Looking for CRM software", email="rahul@example.com",
              phone="+91 9876543210")
HOT = dict(SAMPLE, email="rahul@abctechnologies.com")
COLD = dict(name="A", job_title="Intern", industry="Retail", location="Jaipur", company_size="1-10",
            lead_source="Purchased List", requirement="just exploring free tools for college", email="a@gmail.com", phone="98")


class T(unittest.TestCase):
    def test_weights_sum_100(self): self.assertEqual(sum(WEIGHTS.values()), 100)
    def test_deterministic(self): self.assertEqual(score_lead(SAMPLE).to_dict(), score_lead(dict(SAMPLE)).to_dict())
    def test_sample_is_hot(self): self.assertEqual(score_lead(SAMPLE).classification, "Hot")
    def test_business_email_scores_higher(self): self.assertGreater(score_lead(HOT).score, score_lead(SAMPLE).score)
    def test_cold(self): self.assertEqual(score_lead(COLD).classification, "Cold")
    def test_empty_lead_no_crash(self):
        r = score_lead({}); self.assertEqual(r.confidence, "Low"); self.assertTrue(0 <= r.score <= 100)
    def test_partial_lead_lower_confidence(self):
        self.assertIn(score_lead({"job_title": "CEO", "requirement": "need CRM"}).confidence, ("Low", "Medium"))
    def test_score_range(self):
        for l in (SAMPLE, HOT, COLD, {}): self.assertTrue(0 <= score_lead(l).score <= 100)

if __name__ == "__main__":
    unittest.main()
