# motion-watch

Records video clips and sends email alerts when your laptop camera detects
motion. Runs in the foreground; press Ctrl+C to stop.

## Setup

Copy the example env file and fill in your credentials:

```
cp .env.example .env
```

Edit `.env` with your email address and an
[app password](https://support.google.com/accounts/answer/185833).

---

## macOS

**Requirements:** Python 3.10+

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

Grant your terminal camera access in
**System Settings -> Privacy & Security -> Camera**, then run:

```bash
./run
```

---

## Windows

**Requirements:** [Python 3.10+](https://www.python.org/downloads/) —
check "Add python.exe to PATH" during installation.

```bat
python -m venv venv
venv\Scripts\pip install -r requirements.txt
run
```

---

## Output

Captures are saved to the `captures/` folder:

- `snap_<timestamp>.jpg` — snapshot at first detection
- `clip_<timestamp>.avi` — video clip including 5s pre-motion buffer
- `motion_events.jsonl` — log of all events

To view recent events:

```bash
./run log        # macOS
run log          # Windows
```
