import unittest
from ont_details import parse_cli_properties, parse_ont_details, parse_service_ports


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

    def test_maps_identity_and_valid_connection_times(self):
        info = """ONT SN : 48575444361524D7F
ONT EquipmentID : HG8245H
Description : Customer_01
ONT distance(m) : 1250
Temperature : 43(C)
Last up time : 2026-11-06 10:20:30
Last down time : 2026-11-05 22:10:00
Last down cause : LOS
ONT online duration : 1 day(s), 2 hour(s)
ONT-lineprofile-id : 12
ONT-lineprofile-name : line-profile_12
ONT-srvprofile-id : 15
ONT-srvprofile-name : srv-profile_15
Run state : online
Config state : normal
Match state : match
"""
        optical = """Rx optical power(dBm) : -15.42
Tx optical power(dBm) : 2.10
OLT Rx ONT optical power(dBm) : -20.30
OLT Tx ONT optical power(dBm) : 4.10
Temperature(C) : 27
Voltage(V) : 3.30
Laser bias current(mA) : 10
Module type : GPON
Module sub-type : CLASS B+
Vendor name : HUAWEI
Vendor PN : HW-BOB-0012
Vendor SN : 1627U0213259J
Date Code : 16-08-25
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
        self.assertEqual(result["temperature_c"], "27")
        self.assertEqual(result["ont_temperature"], "43(C)")
        self.assertEqual(result["line_profile_id"], "12")
        self.assertEqual(result["line_profile_name"], "line-profile_12")
        self.assertEqual(result["service_profile_id"], "15")
        self.assertEqual(result["module_subtype"], "CLASS B+")
        self.assertEqual(result["vendor_sn"], "1627U0213259J")
        self.assertTrue(result["connection_timing_valid"])

    def test_flags_epoch_2000_and_implausible_duration(self):
        info = """Last up time : 2000-01-01 00:02:24+03:30
ONT online duration : 9807 day(s), 0 hour(s), 28 minute(s), 15 second(s)
ONT distance(m) : 439
Memory occupation : 40%
CPU occupation : 1%
"""
        optical = """Rx optical power(dBm) : -15.40
Tx optical power(dBm) : 2.09
OLT Rx ONT optical power(dBm) : -16.01
"""
        result = parse_ont_details(info, optical)
        self.assertFalse(result["connection_timing_valid"])
        self.assertIn("سال 2000", result["connection_timing_note"])
        self.assertEqual(result["distance_m"], "439")
        self.assertEqual(result["memory_occupation"], "40%")
        self.assertEqual(result["cpu_occupation"], "1%")
        self.assertEqual(result["olt_rx_power_dbm"], "-16.01")

    def test_parses_service_port_table(self):
        raw = """INDEX VLAN VLAN ATTR PORT TYPE F/S/P VPI VCI FLOW TYPE FLOW PARA RX TX STATE
1000 151 common gpon 0/1 /7 0 2 vlan 151 - - up
Total : 1 (Up/Down : 1/0)
"""
        rows = parse_service_ports(raw)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["index"], "1000")
        self.assertEqual(rows[0]["vlan_id"], "151")
        self.assertEqual(rows[0]["fsp"], "0/1/7")
        self.assertEqual(rows[0]["ont_id"], "0")
        self.assertEqual(rows[0]["gem_id"], "2")
        self.assertEqual(rows[0]["state"], "up")

    def test_missing_fields_remain_missing(self):
        result = parse_ont_details("Run state : offline", "Rx optical power(dBm) : --")
        self.assertIsNone(result["model"])
        self.assertIsNone(result["distance_m"])
        self.assertIsNone(result["tx_power_dbm"])
        self.assertEqual(result["run_state"], "offline")
        self.assertFalse(result["connection_timing_valid"])


if __name__ == "__main__":
    unittest.main()
