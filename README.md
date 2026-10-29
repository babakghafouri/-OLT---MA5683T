# Huawei MA5683T Operator Panel — Windows EXE

This repository is currently being prepared for a Windows build.

## Build the EXE

1. Download the [Windows EXE build kit](https://sandbox:/mnt/data/OLT-MA5683T-Windows-EXE-Build-Kit.zip) from the ChatGPT conversation.
2. Upload that ZIP file to the **root** of this repository using **Add file → Upload files**. Keep its exact name:
   `OLT-MA5683T-Windows-EXE-Build-Kit.zip`
3. Open **Actions → Build Windows EXE → Run workflow**.
4. When the workflow finishes successfully, open the run and download the artifact named `OLT-MA5683T-Panel-Windows`. It contains `OLT-MA5683T-Panel.exe`.

The EXE runs a local web server and opens the panel in the browser at `http://127.0.0.1:8080`.

## Security

- Do not commit OLT usernames/passwords, real device IPs, or other credentials.
- The EXE has not been verified against a live OLT from this build environment.
