# soulkiller

Build a personal engram from lifetime data:

- **Voice**: QLoRA fine-tune of Qwen3 on what *you* wrote (replies in email/chats, posts), so it talks like you.
- **Memory**: a retrieval index over everything (mail, Drive, calendar, notes, lifelog), so it knows your life. *(next step)*

Everything stays local. Data parsing runs on the Mac; training runs on the Linux GPU box.

```
exports ──► soulkiller ingest ──► messages.jsonl / docs.jsonl ──► soulkiller build ──► sft_train.jsonl ──► train/train.py (GPU) ──► LoRA + GGUF
```

## 1. Request your exports (start now: some take days)

Unpack each into `data/raw/<folder>/`. Always pick **JSON** and **All time** where offered.

| Source | How | Folder |
|---|---|---|
| Gmail, Calendar, Drive, YouTube, Chrome | [takeout.google.com](https://takeout.google.com). Select Mail, Calendar, Drive, YouTube, Chrome. **YouTube → "Multiple formats" → history: JSON** (default is HTML). Use 50 GB .tgz parts. | `google/` |
| Maps Timeline | Stored on the phone now: Settings → Location → Location services → Timeline → **Export Timeline data** → `Timeline.json` | `google/` |
| Facebook + Messenger | Accounts Center → Your information and permissions → Download your information → **JSON**, All time. | `facebook/` |
| Messenger encrypted chats | Most DMs since 2024 are E2EE and **missing from the export above**. Messenger → Settings → Privacy & safety → End-to-end encrypted chats → Message storage → **Download secure storage data**. | `facebook/` |
| Instagram | Accounts Center, same flow, JSON | `instagram/` |
| WhatsApp | Each chat → ⋮ → More → Export chat → **Without media**. Do your top ~20 chats. | `whatsapp/` |
| Telegram | Telegram **Desktop** → Settings → Advanced → Export Telegram data → **JSON** | `telegram/` |
| X / Twitter | Settings → Your account → Download an archive | `twitter/` |
| LinkedIn | Settings → Data privacy → Get a copy of your data → full archive | `linkedin/` |
| Reddit | reddit.com/settings/data-request | `reddit/` |
| Notes | Copy Obsidian vault / Markdown / txt in. Apple Notes: export to Markdown first (e.g. the *Exporter* app). | `notes/` |
| Code | `data/raw/git/repos.txt`: one local repo path per line (your commit messages) | `git/` |

**Disk**: a lifetime Takeout can be 20–60 GB. If space is short, put `data/` on an external drive and symlink it.

## 2. Parse (Mac)

```bash
uv sync
uv run soulkiller init        # creates config.toml + data/raw/* folders
# edit config.toml: name, every email you've sent from, every chat display name/handle you've used
uv run soulkiller ingest      # or: --only gmail whatsapp
uv run soulkiller stats       # how many tokens of *you* there are; lists unrecognized senders
uv run soulkiller build       # -> data/processed/sft_train.jsonl, sft_val.jsonl
```

Check the `stats` output for senders that are actually you under another name. Add them to `[me].names` and re-run ingest.
Skim a few lines of `sft_train.jsonl` before training. Garbage in, garbage soul.

## 3. Train (Linux, RTX 4080 Super 16 GB)

```bash
rsync -a --exclude .venv --exclude 'data/raw' ./ gpu-box:soulkiller/
ssh gpu-box
cd soulkiller && python -m venv .venv && . .venv/bin/activate && pip install -r train/requirements.txt
python train/train.py --model unsloth/Qwen3-4B --epochs 1 --out outputs/smoke   # quick sanity run
python train/train.py --model unsloth/Qwen3-8B --out outputs/engram-v1          # the real one
python train/chat.py outputs/engram-v1/lora --with "Anna" --channel WhatsApp
```

Output: `outputs/engram-v1/lora` (adapter) and `outputs/engram-v1/gguf` (for Ollama / llama.cpp / LM Studio on the Mac).

## Privacy

- Training loss is applied **only to your own messages**. Other people's messages appear only as the context you were replying to.
- Passwords, OTP codes, card numbers, IBANs and PESELs are redacted at parse time (best-effort regex, so still review).
- Newsletters and bulk mail are dropped. Spam and Trash are skipped.
- `data/`, `outputs/` and `config.toml` are gitignored. The trained model has memorized private details of you and the people you talk to: **don't publish it**.
