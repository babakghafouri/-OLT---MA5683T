import unittest
from chassis_inventory import parse_chassis_inventory

class ChassisInventoryTests(unittest.TestCase):
    def test_live_rows_and_unknown_slots(self):
        result = parse_chassis_inventory("0 H802GPBD Normal\n6 H801SCUN Standby_normal\n7 H801SCUN Active_normal\n")
        self.assertEqual(len(result["slots"]), 13)
        self.assertEqual(result["slots"][0]["board"], "H802GPBD")
        self.assertEqual(result["slots"][7]["status"], "Active_normal")
        self.assertEqual(result["slots"][1]["state"], "unknown")
    def test_no_fake_hardware_on_error(self):
        result = parse_chassis_inventory("Error: Unknown command")
        self.assertEqual(result["recognized"], 0)
        self.assertTrue(all(s["state"] == "unknown" for s in result["slots"]))
    def test_explicit_empty(self):
        result = parse_chassis_inventory("3 empty")
        self.assertEqual(result["slots"][3]["state"], "empty")
if __name__ == "__main__":
    unittest.main()
