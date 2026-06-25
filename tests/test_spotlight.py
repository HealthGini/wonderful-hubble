import unittest
from base_test import BaseTestCase

class TestSpotlight(BaseTestCase):

    def test_spotlight_default_june(self):
        """Tests default spotlight aggregation (June 2026, offset 0)."""
        status, _, body = self.make_request("GET", "/api/spotlight")
        self.assertEqual(status, 200)
        self.assertEqual(body["month"], "June 2026")
        
        # Verify structure
        self.assertIn("top_kudos_champions", body)
        self.assertIn("top_post_creators", body)
        self.assertIn("valuable_resources", body)

        # Base Kudos Champions check
        # In seed data, Kudos recipients:
        # - Marcus (user 2): received 1 Kudos (Item 1)
        # - Elena (user 3): received 1 Kudos (Item 3)
        # Marcus base_reactions (reactions on Kudos received):
        # Item 1 (Marcus recipient): 3 reactions (❤️, 👏, 🌟)
        # Elena base_reactions (reactions on Kudos received):
        # Item 3 (Elena recipient): 2 reactions (👏, 🎉)
        # So Marcus should be ahead of Elena.
        champions = body["top_kudos_champions"]
        self.assertGreater(len(champions), 0)
        self.assertEqual(champions[0]["username"], "Marcus_Vance")
        if len(champions) > 1:
            self.assertEqual(champions[1]["username"], "Elena_Wellness")

        # Check that values are calculated with multipliers
        # Marcus (idx 0): base_kudos=1, base_reactions=3.
        # mult_k = [14, 11, 9, 7], mult_r = [86, 72, 64, 52]
        # June (offset 0):
        # Marcus: kudos_count = 1 + 14 = 15. total_reactions = 3 + 86 = 89.
        self.assertEqual(champions[0]["kudos_count"], 15)
        self.assertEqual(champions[0]["total_reactions"], 89)

    def test_spotlight_may_rotation(self):
        """Tests spotlight rotation with month offset (May 2026, offset 1)."""
        status, _, body = self.make_request("GET", "/api/spotlight?month=May 2026")
        self.assertEqual(status, 200)
        self.assertEqual(body["month"], "May 2026")

        # With offset 1, the list should be rotated by 1
        # raw_kudos = [Marcus, Elena, ...]
        # rotated = raw_kudos[1:] + raw_kudos[:1] = [Elena, ...]
        
        # Get June data for comparison
        _, _, body_june = self.make_request("GET", "/api/spotlight?month=June 2026")
        champions_june = body_june["top_kudos_champions"]
        champions_may = body["top_kudos_champions"]

        if len(champions_june) > 1:
            self.assertNotEqual(champions_june[0]["username"], champions_may[0]["username"])
            self.assertEqual(champions_may[0]["username"], "Elena_Wellness")

            # Elena (now at idx 0 in May): base_kudos=1, base_reactions=2.
            # May Elena (idx 0, offset 1):
            # kudos_count = base_kudos (1) + mult_k[0] (14) + (offset*3) (3) = 18.
            # total_reactions = base_reactions (2) + mult_r[0] (86) + (offset*10) (10) = 98.
            self.assertEqual(champions_may[0]["kudos_count"], 18)
            self.assertEqual(champions_may[0]["total_reactions"], 98)

    def test_spotlight_resources_aggregation(self):
        """Tests resource aggregation and sorting within spotlight."""
        status, _, body = self.make_request("GET", "/api/spotlight")
        self.assertEqual(status, 200)
        valuable_res = body["valuable_resources"]
        
        # In seed resources:
        # G1: "Mental Health First Aid..." (PDF, Theme: Mental Health)
        # G1: "Free Online Mindfulness..." (URL, Theme: Mental Health)
        # G2: "Comprehensive Resume..." (PDF, Theme: Education)
        # G3: "Local Mutual Aid..." (PDF, Theme: Community Services)
        
        self.assertIn("Mental Health", valuable_res)
        self.assertIn("Education", valuable_res)
        self.assertIn("Community Services", valuable_res)

        # Check sorting by saves within a theme (Mental Health has 2 resources)
        # val_map = [184, 156, 142, ...]
        # For June (offset 0):
        # Res 1 (id 1): saves = val_map[0] = 184
        # Res 2 (id 2): saves = val_map[1] = 156
        # They should be sorted by saves descending.
        mh_res = valuable_res["Mental Health"]
        self.assertEqual(len(mh_res), 2)
        self.assertEqual(mh_res[0]["id"], 1)
        self.assertEqual(mh_res[1]["id"], 2)
        self.assertEqual(mh_res[0]["saves"], 184)
        self.assertEqual(mh_res[1]["saves"], 156)

        # For May (offset 1):
        # Res 1 (id 1): saves = val_map[1] = 156
        # Res 2 (id 2): saves = val_map[2] = 142
        status, _, body_may = self.make_request("GET", "/api/spotlight?month=May 2026")
        mh_res_may = body_may["valuable_resources"]["Mental Health"]
        self.assertEqual(mh_res_may[0]["saves"], 156)
        self.assertEqual(mh_res_may[1]["saves"], 142)

if __name__ == "__main__":
    unittest.main()
