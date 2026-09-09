# EmailSentinel: Priority Inbox Monitor and Triage HUD

An automated, background email triage engine and Live Console HUD engineered for Austin Davis to eliminate email overwhelm, prevent cognitive fatigue, and provide zero-typing triage of critical communications.

---

## Overview

EmailSentinel connects securely to your email inbox using IMAP over SSL (port 993). It continuously scans for new unread communications and instantly correlates senders and message subjects against prioritized categories:

1. **LEGAL**: Tyler Gray, his paralegal, Morgan and Morgan, court notices, and settlement status.
2. **DEVRY ACADEMIC**: Canvas notifications, professors, Judith, Julie, Financial Aid, FAFSA disbursements, and student loans.
3. **MEDICAL**: Bienville Orthopaedic Specialists, doctor notes, radiology, prescriptions, and clinic appointments.
4. **BILLS AND FINANCIAL**: Past due notices, due dates, invoices, statements, utility bills, and payment demands.
5. **SECURITY ALERTS**: 2-Factor Authentication codes, unauthorized access warnings, and password reset requests.

---

## Live Console HUD Features

* **Real-Time Telemetry Panel**: Displays connection status, active polling countdown timer, and monitored priority categories.
* **Dual Notification Pipeline**:
  * **Windows Desktop Toast**: Native pop-up notification appearing in the bottom-right corner of your screen.
  * **Windows SAPI Voice Announcement**: Speaks the category, sender, and subject through your speakers.
* **Single-Key Ergonomic Controls (Zero Typing)**:
  * `[S]`: Trigger instant inbox scan now.
  * `[O]`: Open Gmail in your default browser.
  * `[T]`: Send a test notification alert and speech sample.
  * `[M]`: Toggle audio alerts on or off.
  * `[Q]`: Cleanly exit the Sentinel HUD.

---

## Setup Instructions

1. Open `config.json` in `C:\Users\daddy\Desktop\EmailSentinel\config.json`.
2. Enter your 16-character Google App Password in the `"email_pass"` field:
   * To generate a Google App Password:
     1. Visit: `https://myaccount.google.com/apppasswords`
     2. Name it "EmailSentinel".
     3. Copy the 16-letter code into `"email_pass"` in `config.json`.
3. Launch EmailSentinel:
   * Double-click `EmailSentinel.lnk` on your Desktop, or run `Launch_Sentinel.bat`.
