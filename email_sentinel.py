import os
import sys
import json
import time
import email
import socket
import imaplib
import threading
import msvcrt
import webbrowser
import ctypes
from datetime import datetime
from email.header import decode_header
from PIL import Image

import pystray
from pystray import MenuItem as item
import win32gui
import win32con

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live

import notifier

APP_TITLE = "EmailSentinel: Priority Inbox Monitor"
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
HISTORY_PATH = os.path.join(os.path.dirname(__file__), "alerts_history.json")
SEEN_PATH = os.path.join(os.path.dirname(__file__), "processed_ids.json")
ICO_PATH = os.path.join(os.path.dirname(__file__), "emailsentinel.ico")

console = Console()

# Inject Windows Taskbar AppUserModelID and window icon
try:
    myappid = "DaddyDavis.EmailSentinel.LiveHUD.1.0"
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    if hwnd and os.path.exists(ICO_PATH):
        h_icon = ctypes.windll.user32.LoadImageW(None, ICO_PATH, 1, 32, 32, 0x00000010 | 0x00000040)
        if h_icon:
            ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 1, h_icon)
            ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 0, h_icon)
except Exception:
    pass

class EmailSentinel:
    def __init__(self):
        self.lock_mutex = self.acquire_single_instance_lock()
        self.config = self.load_config()
        self.running = True
        self.last_scan_time = "Never"
        self.connection_status = "INITIALIZING"
        self.status_detail = "Calibrating baseline..."
        self.next_poll_countdown = self.config.get("poll_interval_seconds", 60)
        self.processed_ids = self.load_processed_ids()
        self.baseline_established = len(self.processed_ids) > 0
        self.alerts_history = self.load_history()
        self.sound_enabled = self.config.get("sound_alerts", True)
        self.voice_enabled = self.config.get("voice_tts", True)
        self.toast_enabled = self.config.get("toast_notifications", True)
        self.tray_icon = None

    def acquire_single_instance_lock(self):
        """Prevent multiple instances. If one exists, restore and bring it to front."""
        try:
            import win32event, win32api, winerror
            mutex = win32event.CreateMutex(None, False, "Global\\EmailSentinel_SingleInstance_Mutex")
            if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
                console.print(f"\n[bold yellow]EmailSentinel is already active in your Taskbar / System Tray.[/bold yellow]")
                console.print("[white]Bringing active window to front...[/white]\n")
                # Unhide existing window and bring to foreground
                hwnd = win32gui.FindWindow(None, APP_TITLE)
                if hwnd:
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    win32gui.SetForegroundWindow(hwnd)
                time.sleep(2)
                sys.exit(0)
            return mutex
        except Exception:
            return None

    def load_config(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def load_processed_ids(self):
        if os.path.exists(SEEN_PATH):
            try:
                with open(SEEN_PATH, "r", encoding="utf-8") as f:
                    return set(json.load(f))
            except Exception:
                pass
        return set()

    def save_processed_ids(self):
        try:
            with open(SEEN_PATH, "w", encoding="utf-8") as f:
                json.dump(list(self.processed_ids)[-1000:], f)
        except Exception:
            pass

    def load_history(self):
        if os.path.exists(HISTORY_PATH):
            try:
                with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def save_history(self):
        try:
            with open(HISTORY_PATH, "w", encoding="utf-8") as f:
                json.dump(self.alerts_history[-100:], f, indent=2)
        except Exception:
            pass

    def decode_mime_words(self, raw_header):
        if not raw_header:
            return ""
        try:
            decoded_list = decode_header(raw_header)
            parts = []
            for text, encoding in decoded_list:
                if isinstance(text, bytes):
                    parts.append(text.decode(encoding if encoding else "utf-8", errors="ignore"))
                else:
                    parts.append(str(text))
            return "".join(parts)
        except Exception:
            return str(raw_header)

    def classify_email(self, sender, subject, body_snippet=""):
        combined_text = f"{sender} {subject} {body_snippet}".lower()
        categories = self.config.get("priority_categories", {})

        matched_category = None
        highest_score = 0
        matched_keyword = None

        for cat_name, cat_data in categories.items():
            keywords = cat_data.get("keywords", [])
            score = cat_data.get("priority_score", 5)
            for kw in keywords:
                if kw.lower() in combined_text:
                    if score > highest_score:
                        highest_score = score
                        matched_category = cat_name
                        matched_keyword = kw

        return matched_category, highest_score, matched_keyword

    def check_inbox(self):
        user = self.config.get("email_user", "")
        password = self.config.get("email_pass", "").strip()
        server_host = self.config.get("imap_server", "imap.gmail.com")
        port = self.config.get("imap_port", 993)

        if not password:
            self.connection_status = "AUTH REQUIRED"
            self.status_detail = "Add Google App Password to config.json"
            return

        try:
            self.connection_status = "CONNECTING"
            mail = imaplib.IMAP4_SSL(server_host, port)
            mail.login(user, password)
            self.connection_status = "ONLINE"
            mail.select("INBOX", readonly=True)

            # First-Run Baseline Calibration: Ignore all historical emails
            if not self.baseline_established:
                self.status_detail = "Calibrating baseline... ignoring old emails"
                status, unread_resp = mail.search(None, "UNSEEN")
                if status == "OK" and unread_resp[0]:
                    for mid in unread_resp[0].split():
                        self.processed_ids.add(mid.decode("utf-8", errors="ignore"))

                status, all_resp = mail.search(None, "ALL")
                if status == "OK" and all_resp[0]:
                    for mid in all_resp[0].split()[-100:]:
                        self.processed_ids.add(mid.decode("utf-8", errors="ignore"))

                self.baseline_established = True
                self.save_processed_ids()
                self.last_scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.status_detail = f"Baseline locked. Ignored {len(self.processed_ids)} old emails."
                mail.close()
                mail.logout()
                return

            # Routine Polling: Only check unread (UNSEEN) emails
            status, unread_resp = mail.search(None, "UNSEEN")
            candidate_ids = []
            if status == "OK" and unread_resp[0]:
                candidate_ids = unread_resp[0].split()

            new_alerts_count = 0

            for msg_id in candidate_ids:
                msg_id_str = msg_id.decode("utf-8") if isinstance(msg_id, bytes) else str(msg_id)
                if msg_id_str in self.processed_ids:
                    continue

                self.processed_ids.add(msg_id_str)
                self.save_processed_ids()

                status, data = mail.fetch(msg_id, "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE)])")
                if status != "OK" or not data or not data[0]:
                    continue

                raw_email_bytes = data[0][1]
                msg = email.message_from_bytes(raw_email_bytes)

                sender = self.decode_mime_words(msg.get("From", "Unknown"))
                subject = self.decode_mime_words(msg.get("Subject", "No Subject"))

                category, score, keyword = self.classify_email(sender, subject)

                if category:
                    alert_item = {
                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                        "category": category,
                        "score": score,
                        "sender": notifier.sanitize_text(sender),
                        "subject": notifier.sanitize_text(subject),
                        "keyword": keyword
                    }
                    self.alerts_history.insert(0, alert_item)
                    self.save_history()
                    new_alerts_count += 1

                    # Trigger audio and toast notifications
                    notifier.trigger_notification(
                        category,
                        sender,
                        subject,
                        toast=self.toast_enabled,
                        voice=self.voice_enabled
                    )

            self.last_scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if new_alerts_count > 0:
                self.status_detail = f"New alert: {new_alerts_count} priority email(s) found!"
            else:
                self.status_detail = "Inbox clear. No new priority messages."

            mail.close()
            mail.logout()

        except imaplib.IMAP4.error:
            self.connection_status = "AUTH FAILED"
            self.status_detail = "Invalid Google App Password."
        except Exception as e:
            self.connection_status = "ERROR"
            self.status_detail = notifier.sanitize_text(str(e))[:50]

    def background_poll_worker(self):
        while self.running:
            self.check_inbox()
            interval = self.config.get("poll_interval_seconds", 60)
            self.next_poll_countdown = interval
            while self.next_poll_countdown > 0 and self.running:
                time.sleep(1)
                self.next_poll_countdown -= 1

    def show_console(self):
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)

    def hide_console(self):
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            win32gui.ShowWindow(hwnd, win32con.SW_HIDE)

    def setup_tray_icon(self):
        if not os.path.exists(ICO_PATH):
            return
        try:
            image = Image.open(ICO_PATH)
            menu = pystray.Menu(
                item("Show Console HUD", lambda: self.show_console(), default=True),
                item("Hide to System Tray", lambda: self.hide_console()),
                pystray.Menu.SEPARATOR,
                item("Scan Inbox Now", lambda: threading.Thread(target=self.check_inbox, daemon=True).start()),
                item("Test Alert", lambda: notifier.trigger_notification("LEGAL", "Tyler Gray", "Test settlement alert", toast=True, voice=True)),
                item("Open Web Gmail", lambda: webbrowser.open("https://mail.google.com")),
                pystray.Menu.SEPARATOR,
                item("Quit EmailSentinel", lambda: self.quit_app())
            )
            self.tray_icon = pystray.Icon("EmailSentinel", image, APP_TITLE, menu)
            self.tray_icon.run()
        except Exception:
            pass

    def quit_app(self):
        self.running = False
        if self.tray_icon:
            self.tray_icon.stop()
        sys.exit(0)

    def build_layout(self):
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=3)
        )

        header_text = Text()
        header_text.append("EMAIL SENTINEL ", style="bold green")
        header_text.append("| PRIORITY INBOX MONITOR & RAPID TRIAGE HUD", style="bold white")
        header_panel = Panel(header_text, style="green on #030508", border_style="green")
        layout["header"].update(header_panel)

        layout["main"].split_row(
            Layout(name="status_panel", ratio=1),
            Layout(name="alerts_table", ratio=2)
        )

        status_table = Table(box=None, expand=True, show_header=False)
        status_table.add_column("Key", style="bold cyan", width=16)
        status_table.add_column("Val", style="bold white")

        status_table.add_row("Email Account", self.config.get("email_user", "N/A"))
        status_table.add_row("Server", f"{self.config.get('imap_server', 'imap.gmail.com')}:{self.config.get('imap_port', 993)}")

        stat_color = "green" if self.connection_status == "ONLINE" else "red" if "AUTH" in self.connection_status else "yellow"
        status_table.add_row("Status", f"[{stat_color}]{self.connection_status}[/{stat_color}]")
        status_table.add_row("Detail", self.status_detail[:35])
        status_table.add_row("Last Scanned", self.last_scan_time)
        status_table.add_row("Next Poll In", f"{self.next_poll_countdown} seconds")
        status_table.add_row("Audio Alerts", "[green]ENABLED[/green]" if self.sound_enabled else "[dim]MUTED[/dim]")
        status_table.add_row("Toast Popups", "[green]ENABLED[/green]" if self.toast_enabled else "[dim]DISABLED[/dim]")

        channels_text = Text("\nACTIVE PRIORITY WATCHLIST:\n", style="bold yellow")
        channels_text.append("[LEGAL] ", style="bold red")
        channels_text.append("Tyler Gray, Morgan and Morgan, Court\n", style="white")
        channels_text.append("[ACADEMIC] ", style="bold cyan")
        channels_text.append("DeVry, Canvas, Judith, Julie, Aid\n", style="white")
        channels_text.append("[MEDICAL] ", style="bold magenta")
        channels_text.append("Bienville Ortho, Appointments, Prescriptions\n", style="white")
        channels_text.append("[FINANCIAL] ", style="bold green")
        channels_text.append("Past Due, Invoices, Due Dates, Utilities\n", style="white")

        status_content = Layout()
        status_content.split_column(
            Layout(status_table, size=9),
            Layout(channels_text)
        )
        layout["main"]["status_panel"].update(Panel(status_content, title="Sentinel Telemetry", border_style="cyan"))

        alerts_table = Table(expand=True, border_style="blue")
        alerts_table.add_column("Time", style="dim", width=10)
        alerts_table.add_column("Category", style="bold", width=16)
        alerts_table.add_column("Sender", style="cyan", width=22)
        alerts_table.add_column("Subject", style="white")

        if not self.alerts_history:
            alerts_table.add_row("--:--:--", "[INFO] IDLE", "Sentinel Daemon", "Listening for incoming priority messages...")
        else:
            for item in self.alerts_history[:10]:
                cat = item.get("category", "INFO")
                color = "red" if cat == "LEGAL" else "cyan" if "DEVRY" in cat else "magenta" if cat == "MEDICAL" else "green"
                alerts_table.add_row(
                    item.get("timestamp", "--:--:--"),
                    f"[{color}]{cat}[/{color}]",
                    item.get("sender", "Unknown")[:20],
                    item.get("subject", "No Subject")[:45]
                )

        layout["main"]["alerts_table"].update(Panel(alerts_table, title="Live Priority Triage Alerts", border_style="green"))

        footer_text = Text(" CONTROLS: ", style="bold yellow")
        footer_text.append("[H] ", style="bold cyan")
        footer_text.append("Hide to Tray  |  ", style="white")
        footer_text.append("[S] ", style="bold green")
        footer_text.append("Scan Now  |  ", style="white")
        footer_text.append("[O] ", style="bold cyan")
        footer_text.append("Open Gmail  |  ", style="white")
        footer_text.append("[T] ", style="bold magenta")
        footer_text.append("Test Alert  |  ", style="white")
        footer_text.append("[M] ", style="bold yellow")
        footer_text.append("Toggle Audio  |  ", style="white")
        footer_text.append("[Q] ", style="bold red")
        footer_text.append("Quit", style="white")

        footer_panel = Panel(footer_text, style="white on #030508", border_style="yellow")
        layout["footer"].update(footer_panel)

        return layout

    def run(self):
        worker_thread = threading.Thread(target=self.background_poll_worker, daemon=True)
        worker_thread.start()

        tray_thread = threading.Thread(target=self.setup_tray_icon, daemon=True)
        tray_thread.start()

        with Live(self.build_layout(), refresh_per_second=2, screen=True) as live:
            while self.running:
                if msvcrt.kbhit():
                    ch = msvcrt.getch().decode("utf-8", errors="ignore").lower()
                    if ch == "q":
                        self.quit_app()
                        break
                    elif ch == "h":
                        self.hide_console()
                    elif ch == "s":
                        threading.Thread(target=self.check_inbox, daemon=True).start()
                    elif ch == "o":
                        webbrowser.open("https://mail.google.com")
                    elif ch == "t":
                        notifier.trigger_notification(
                            "LEGAL",
                            "Tyler Gray (Morgan and Morgan)",
                            "Test alert: Settlement update review",
                            toast=self.toast_enabled,
                            voice=self.voice_enabled
                        )
                    elif ch == "m":
                        self.sound_enabled = not self.sound_enabled
                        self.voice_enabled = not self.voice_enabled

                live.update(self.build_layout())
                time.sleep(0.5)

def main():
    sentinel = EmailSentinel()
    sentinel.run()

if __name__ == "__main__":
    main()
