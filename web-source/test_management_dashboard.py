import unittest
from unittest.mock import patch

import app as app_module


class ManagementDashboardTests(unittest.TestCase):
    def setUp(self):
        self.old_password = app_module.UI_PASSWORD
        app_module.UI_PASSWORD = ""
        self.client = app_module.app.test_client()

    def tearDown(self):
        app_module.UI_PASSWORD = self.old_password

    def test_management_page_is_separate_from_operator_home(self):
        response = self.client.get("/management")
        self.assertEqual(response.status_code, 200)
        self.assertIn("داشبورد مدیریتی".encode(), response.data)
        operator = self.client.get("/")
        self.assertEqual(operator.status_code, 200)
        self.assertIn("داشبورد اپراتور".encode(), operator.data)

    def test_select_device_requires_existing_session(self):
        devices = [{"id": "olt-1", "name": "OLT 1"}]
        with patch.object(app_module, "load_devices", return_value=devices), \
             patch.object(app_module.MANAGER, "get", return_value=None):
            response = self.client.post("/api/select-device", json={"device_id": "olt-1"})
        self.assertEqual(response.status_code, 409)

    def test_select_device_activates_existing_session(self):
        class DummyConnection:
            host = "192.0.2.10"
            proto = "ssh"

        devices = [{"id": "olt-1", "name": "OLT 1"}]
        with patch.object(app_module, "load_devices", return_value=devices), \
             patch.object(app_module.MANAGER, "get", return_value=DummyConnection()):
            response = self.client.post("/api/select-device", json={"device_id": "olt-1"})
        self.assertEqual(response.status_code, 200)
        with self.client.session_transaction() as sess:
            self.assertEqual(sess["active_olt_id"], "olt-1")

    def test_update_device_refuses_to_change_live_connection(self):
        devices = [{"id": "olt-1", "name": "OLT 1", "host": "192.0.2.10",
                    "port": 23, "proto": "telnet", "credential_mode": "session"}]
        with patch.object(app_module, "load_devices", return_value=devices), \
             patch.object(app_module.MANAGER, "get", return_value=object()):
            response = self.client.put("/api/devices/olt-1", json={
                "name": "OLT renamed", "host": "192.0.2.11", "proto": "ssh", "port": 22,
                "credential_mode": "session"
            })
        self.assertEqual(response.status_code, 409)

    def test_switching_to_session_mode_removes_persisted_credentials(self):
        devices = [{"id": "olt-1", "name": "OLT old", "host": "192.0.2.10",
                    "port": 23, "proto": "telnet", "credential_mode": "encrypted",
                    "username": "operator", "password_enc": "ciphertext", "notes": ""}]
        with patch.object(app_module, "load_devices", return_value=devices), \
             patch.object(app_module, "save_devices") as save, \
             patch.object(app_module.MANAGER, "get", return_value=None):
            response = self.client.put("/api/devices/olt-1", json={
                "name": "OLT new", "host": "192.0.2.11", "proto": "ssh", "port": 22,
                "credential_mode": "session", "notes": "updated"
            })
        self.assertEqual(response.status_code, 200)
        saved = save.call_args.args[0][0]
        self.assertEqual(saved["name"], "OLT new")
        self.assertNotIn("username", saved)
        self.assertNotIn("password_enc", saved)

    def test_disconnect_device_clears_current_selection(self):
        devices = [{"id": "olt-1", "name": "OLT 1"}]
        with self.client.session_transaction() as sess:
            sess["active_olt_id"] = "olt-1"
        with patch.object(app_module, "load_devices", return_value=devices), \
             patch.object(app_module.MANAGER, "remove") as remove:
            response = self.client.post("/api/devices/olt-1/disconnect", json={})
        self.assertEqual(response.status_code, 200)
        remove.assert_called_once_with("olt-1")
        with self.client.session_transaction() as sess:
            self.assertNotIn("active_olt_id", sess)


if __name__ == "__main__":
    unittest.main()
