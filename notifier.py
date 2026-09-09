import subprocess
import threading
import winsound
import re

try:
    import win32com.client
    import pythoncom
    HAS_SAPI = True
except ImportError:
    HAS_SAPI = False

def sanitize_text(text):
    """Ensure text strictly uses alphanumeric characters and basic punctuation."""
    if not text:
        return ""
    clean = re.sub(r'[^\x20-\x7E]', ' ', text)
    clean = clean.replace("'", "").replace('"', '').replace('`', '')
    return clean.strip()

def _run_toast(title, message):
    safe_title = sanitize_text(title)
    safe_msg = sanitize_text(message)
    ps_cmd = f"""
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
    $textNodes = $template.GetElementsByTagName('text')
    $textNodes.Item(0).AppendChild($template.CreateTextNode('{safe_title}')) | Out-Null
    $textNodes.Item(1).AppendChild($template.CreateTextNode('{safe_msg}')) | Out-Null
    $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('EmailSentinel').Show($toast)
    """
    try:
        subprocess.run(
            ['powershell', '-NoProfile', '-WindowStyle', 'Hidden', '-Command', ps_cmd],
            capture_output=True,
            timeout=8
        )
    except Exception:
        pass

def _run_voice(text):
    try:
        # High-tech acoustic dual chime
        winsound.Beep(880, 100)
        winsound.Beep(1320, 150)
        if HAS_SAPI:
            pythoncom.CoInitialize()
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            speaker.Rate = 1
            speaker.Speak(text)
            pythoncom.CoUninitialize()
    except Exception:
        pass

def trigger_notification(category, sender, subject, toast=True, voice=True):
    safe_sender = sanitize_text(sender)
    safe_subj = sanitize_text(subject)

    # Clean short summary for voice
    voice_phrase = f"Priority email received. Category {category}. From {safe_sender[:30]}. Subject {safe_subj[:40]}."

    if toast:
        toast_title = f"EmailSentinel: [{category}]"
        toast_body = f"From: {safe_sender[:45]}\n{safe_subj[:80]}"
        t1 = threading.Thread(target=_run_toast, args=(toast_title, toast_body), daemon=True)
        t1.start()

    if voice:
        t2 = threading.Thread(target=_run_voice, args=(voice_phrase,), daemon=True)
        t2.start()
