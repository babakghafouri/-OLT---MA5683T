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
    def test_real_ma5683t_inventory(self):
        raw = """SlotID  BoardName  Status          SubType0 SubType1    Online/Offline
  0       H807GPBD   Normal
  1       H807GPBD   Normal
  2
  3
  4
  5
  6       H801SCUN   Standby_normal
  7       H801SCUN   Active_normal
  8       H801GICF   Normal
  9       H801GICF   Normal
  10
  11
  12
"""
        result = parse_chassis_inventory(raw)
        self.assertEqual(result["recognized"], 13)
        self.assertEqual([s["slot"] for s in result["slots"] if s["state"] == "installed"], [0, 1, 6, 7, 8, 9])
        self.assertEqual([s["slot"] for s in result["slots"] if s["state"] == "empty"], [2, 3, 4, 5, 10, 11, 12])
        self.assertEqual(result["slots"][6]["status"], "Standby_normal")
        self.assertEqual(result["slots"][7]["status"], "Active_normal")

    def test_explicit_empty(self):
        result = parse_chassis_inventory("3 empty")
        self.assertEqual(result["slots"][3]["state"], "empty")
    def test_parse_board_ports_only_explicit_matching_slot(self):
        from chassis_inventory import parse_board_ports
        raw = "Port 0/0/0 is up\\nPort 0/0/1 is down\\nPort 0/1/0 is up\\n"
        self.assertEqual(parse_board_ports(raw, 0), ["0/0/0", "0/0/1"])
        self.assertEqual(parse_board_ports(raw, 1), ["0/1/0"])

    def test_parse_board_ports_no_inference(self):
        from chassis_inventory import parse_board_ports
        self.assertEqual(parse_board_ports("Port 0: Up\\nPort 1: Down", 0), [])

    def test_h807gpbd_has_eight_gpon_ports(self):
        from chassis_inventory import gpon_port_count
        self.assertEqual(gpon_port_count("H807GPBD"), 8)
        self.assertIsNone(gpon_port_count("H801SCUN"))

if __name__ == "__main__":
    unittest.main()
