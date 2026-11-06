import unittest
from ont_details import parse_cli_properties, parse_ont_details


class OntDetailsTests(unittest.TestCase):
    def test_extracts_only_label_value_rows_and_hides_password(self):
        raw = """Command: display ont info 0 1 7 0
ONT SN : 48575444361524D7F
Description : Customer_01
Password : secret-value
Port table has no colon
"""
        rows = parse_cli_properties(raw)
        self.assertEqual([x["key"] for x in rows], ["ontsn", "description"])
        self.assertNotIn("secret-value", str(rows))

    def test_maps_identity_optical_and_history_fields(self):
        info = """ONT SN : 48575444361524D7F
ONT EquipmentID : HG8245H
Description : Customer_01
ONT distance(m) : 1250
Last up time : 2026-11-06 10:20:30
Last down time : 2026-11-05 22:10:00
Last down cause : LOS
ONT online duration : 1 day(s), 2 hour(s)
ONT-lineprofile-id : 12
ONT-srvprofile-id : 15
Run state : online
Config state : normal
Match state : match
"""
        optical = """Rx optical power(dBm) : -15.42
Tx optical power(dBm) : 2.10
OLT Rx ONT optical power(dBm) : -20.30
OLT Tx ONT optical power(dBm) : 4.10
Temperature(C) : 41
Voltage(V) : 3.30
Bias current(mA) : 10
"""
        result = parse_ont_details(info, optical)
        self.assertEqual(result["serial_number"], "48575444361524D7F")
        self.assertEqual(result["model"], "HG8245H")
        self.assertEqual(result["description"], "Customer_01")
        self.assertEqual(result["distance_m"], "1250")
        self.assertEqual(result["last_down_cause"], "LOS")
        self.assertEqual(result["rx_power_dbm"], "-15.42")
        self.assertEqual(result["tx_power_dbm"], "2.10")
        self.assertEqual(result["olt_rx_power_dbm"], "-20.30")
        self.assertEqual(result["temperature_c"], "41")
        self.assertEqual(result["line_profile_id"], "12")
        self.assertEqual(result["service_profile_id"], "15")

    def test_missing_fields_remain_missing(self):
        result = parse_ont_details("Run state : offline", "Rx optical power(dBm) : --")
        self.assertIsNone(result["model"])
        self.assertIsNone(result["distance_m"])
        self.assertIsNone(result["tx_power_dbm"])
        self.assertEqual(result["run_state"], "offline")


if __name__ == "__main__":
    unittest.main()
