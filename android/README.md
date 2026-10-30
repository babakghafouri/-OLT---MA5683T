# OLT Monitor for Android

Initial Android client prototype for Huawei MA5683T. It connects directly to the OLT over SSH.

- Live interface traffic: RX/TX Kbit/s and packets/s
- CPU, memory, temperature, FAN and selected board uplink
- Configurable frame/slot/port and polling interval
- SSH credentials are entered at runtime and not persisted

Build from this directory with Android Studio or `gradle :app:assembleDebug`.

The APK is built automatically by the GitHub Actions workflow `Build Android APK` on updates to this branch.

This prototype accepts the SSH host key without pinning. Add host-key verification before production use. CLI prompt behavior may vary by firmware/account privilege; validate against the target MA5683T.
