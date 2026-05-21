#!/usr/bin/env python3
"""
Motion detection tool using the built-in camera.

Usage:
  python3 motion-watch.py        — start watching (foreground, Ctrl+C to stop)
  python3 motion-watch.py log    — print recent motion events

Copy .env.example to .env and fill in your email credentials before running.

Camera permission on macOS: grant Terminal access in
  System Settings -> Privacy & Security -> Camera
"""

import os
import sys
import time
import signal
import datetime
import smtplib
import json
import shutil
import collections
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from pathlib import Path
import cv2
import imutils

from dotenv import load_dotenv
load_dotenv()


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Minimum contour area (pixels²) that counts as motion.
# Raise to ignore small objects; lower to catch subtle movement.
SENSITIVITY = 3000

# Seconds after start before motion tracking, saving, and email alerts begin.
# Also used as the cooldown between repeat email alerts.
DELAY_SECS = 180

# Email settings — loaded from .env file.
EMAIL_SENDER = os.environ["EMAIL_SENDER"]
EMAIL_SENDER_PASSWORD = os.environ["EMAIL_SENDER_PASSWORD"]
EMAIL_RECIPIENT = os.environ["EMAIL_RECIPIENT"]
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))

# Where captures and logs are written.
OUTPUT_DIR = Path(__file__).parent / "captures"

# Toggle file saving.
SAVE_SNAPSHOTS = True
SAVE_VIDEO = True

# Video codec and frame rate.
VIDEO_CODEC = "MJPG"
VIDEO_FPS = 10.0

# How many frames to skip when adapting the background model.
# Higher = slower adaptation (better for stable scenes).
BG_ADAPT_RATE = 0.05

# How many seconds of pre-motion video buffer to keep in memory.
PRE_BUFFER_SECS = 5

# Seconds of no motion before the current clip is closed.
MOTION_END_SECS = 30

# Minimum seconds between snapshots during continuous motion.
SNAPSHOT_INTERVAL_SECS = 10

# Flush the in-memory event list to disk at least every N events.
EVENT_FLUSH_INTERVAL = 10

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ts() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _file_ts() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

def _log(msg: str):
    print(f"[{_ts()}] {msg}", flush=True)

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

def send_alert_email(snapshot_path: Path | None = None):
    subject = "Motion detected on your laptop"
    body = (
        f"Motion was detected at {_ts()}.\n\n"
        "Your laptop's camera recorded movement."
    )
    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECIPIENT
    msg.attach(MIMEText(body, "plain"))

    if snapshot_path and snapshot_path.exists():
        with open(snapshot_path, "rb") as f:
            img_data = f.read()
        image = MIMEImage(img_data, name=snapshot_path.name)
        msg.attach(image)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_SENDER_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, msg.as_string())
        _log(f"Alert email sent to {EMAIL_RECIPIENT}")
        return True
    except Exception as e:
        _log(f"Failed to send email: {e}")
        return False

# ---------------------------------------------------------------------------
# Detection loop
# ---------------------------------------------------------------------------

def run_detector():
    # Clear all output from the previous run on start.
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        _log("ERROR: Cannot open camera.")
        sys.exit(1)

    _log("Camera opened. Warming up background model...")

    ok, frame = cap.read()
    if not ok:
        _log("ERROR: Cannot read from camera.")
        sys.exit(1)

    h, w = frame.shape[:2]
    avg_frame = None

    pre_buffer: collections.deque = collections.deque(
        maxlen=int(PRE_BUFFER_SECS * VIDEO_FPS)
    )

    video_writer = None
    video_path: Path | None = None

    start_time = time.time()
    last_alert_time = 0.0
    last_snapshot_time = 0.0
    motion_events: list[dict] = []
    frames_since_motion = 0
    MOTION_END_FRAMES = int(VIDEO_FPS * MOTION_END_SECS)

    event_log_path = OUTPUT_DIR / "motion_events.jsonl"

    def flush_events():
        with open(event_log_path, "a") as f:
            for ev in motion_events:
                f.write(json.dumps(ev) + "\n")
        motion_events.clear()

    def close_video():
        nonlocal video_writer, video_path
        if video_writer is not None:
            video_writer.release()
            _log(f"Video saved: {video_path}")
            video_writer = None
            video_path = None

    def handle_shutdown(signum, frame_):
        _log("Shutting down — flushing data to disk...")
        flush_events()
        close_video()
        cap.release()
        _log("Done. Goodbye.")
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    _log(
        f"Watching. Motion tracking begins in {DELAY_SECS}s. "
        f"Output dir: {OUTPUT_DIR}"
    )

    consecutive_flush = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            _log("WARNING: Frame grab failed, retrying...")
            time.sleep(0.1)
            continue

        now = time.time()
        frame_small = imutils.resize(frame, width=500)
        gray = cv2.cvtColor(frame_small, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        if avg_frame is None:
            avg_frame = gray.copy().astype("float")
            pre_buffer.append((now, frame.copy()))
            continue

        cv2.accumulateWeighted(gray, avg_frame, BG_ADAPT_RATE)
        delta = cv2.absdiff(gray, cv2.convertScaleAbs(avg_frame))
        thresh = cv2.threshold(delta, 25, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=2)
        cnts = cv2.findContours(
            thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        cnts = imutils.grab_contours(cnts)

        motion_detected = any(
            cv2.contourArea(c) >= SENSITIVITY for c in cnts
        )

        elapsed = now - start_time
        active = elapsed >= DELAY_SECS

        if motion_detected and active:
            frames_since_motion = 0
            event_ts = _ts()
            file_ts = _file_ts()

            snap_path: Path | None = None
            if SAVE_SNAPSHOTS and (now - last_snapshot_time) >= SNAPSHOT_INTERVAL_SECS:
                snap_path = OUTPUT_DIR / f"snap_{file_ts}.jpg"
                cv2.imwrite(str(snap_path), frame)
                last_snapshot_time = now

            if SAVE_VIDEO:
                if video_writer is None:
                    video_path = OUTPUT_DIR / f"clip_{file_ts}.avi"
                    fourcc = cv2.VideoWriter_fourcc(*VIDEO_CODEC)
                    video_writer = cv2.VideoWriter(
                        str(video_path), fourcc, VIDEO_FPS, (w, h)
                    )
                    for _, buf_frame in pre_buffer:
                        video_writer.write(buf_frame)

            ev = {
                "timestamp": event_ts,
                "snapshot": str(snap_path) if snap_path else None,
            }
            motion_events.append(ev)
            consecutive_flush += 1

            if consecutive_flush >= EVENT_FLUSH_INTERVAL:
                flush_events()
                consecutive_flush = 0

            cooldown_passed = (now - last_alert_time) >= DELAY_SECS
            if cooldown_passed:
                _log("Motion detected — sending alert")
                send_alert_email(snap_path)
                last_alert_time = now
            else:
                _log("Motion detected (alert on cooldown)")

        elif motion_detected:
            remaining = int(DELAY_SECS - elapsed)
            _log(f"Motion detected (warming up, {remaining}s remaining)")

        else:
            frames_since_motion += 1
            if frames_since_motion >= MOTION_END_FRAMES:
                close_video()

        if video_writer is not None:
            video_writer.write(frame)

        pre_buffer.append((now, frame.copy()))

        if len(motion_events) > 0 and consecutive_flush == 0:
            flush_events()

# ---------------------------------------------------------------------------
# Log command
# ---------------------------------------------------------------------------

def cmd_log(n: int = 20):
    event_log = OUTPUT_DIR / "motion_events.jsonl"
    if not event_log.exists():
        print("No motion events recorded yet.")
        return
    with open(event_log) as f:
        lines = f.readlines()
    recent = lines[-n:]
    print(f"Last {len(recent)} motion events:")
    for line in recent:
        try:
            ev = json.loads(line)
            snap = ev.get("snapshot") or "no snapshot"
            print(f"  {ev['timestamp']}  {snap}")
        except json.JSONDecodeError:
            print(f"  {line.rstrip()}")

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cmd = sys.argv[1].lower() if len(sys.argv) > 1 else "run"

    if cmd in ("run", "start"):
        run_detector()
    elif cmd == "log":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        cmd_log(n)
    else:
        print(f"Unknown command: {cmd}")
        print("Usage: python3 motion-watch.py [log [N]]")
        sys.exit(1)
