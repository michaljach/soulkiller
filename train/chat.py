"""Talk to the trained adapter on the GPU box.

    python train/chat.py outputs/engram/lora --with "Anna Nowak" --channel WhatsApp
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from unsloth import FastLanguageModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from soulkiller import config as config_mod  # noqa: E402
from soulkiller.build import system_prompt  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("adapter")
p.add_argument("--config", default="config.toml")
p.add_argument("--with", dest="others", nargs="*", default=[])
p.add_argument("--channel", default="Messenger")
p.add_argument("--temperature", type=float, default=0.8)
args = p.parse_args()

cfg = config_mod.load(args.config)
model, tokenizer = FastLanguageModel.from_pretrained(args.adapter, max_seq_length=4096, load_in_4bit=True)
FastLanguageModel.for_inference(model)
history = [{"role": "system", "content": system_prompt(cfg.name, args.channel, args.others, date.today().isoformat())}]
print(history[0]["content"], "\n(ctrl-d to quit)")
while True:
    try:
        history.append({"role": "user", "content": input("> ")})
    except EOFError:
        break
    ids = tokenizer.apply_chat_template(history, add_generation_prompt=True, enable_thinking=False,
                                        return_tensors="pt").to("cuda")
    out = model.generate(ids, max_new_tokens=400, temperature=args.temperature, top_p=0.9, do_sample=True)
    reply = tokenizer.decode(out[0, ids.shape[1]:], skip_special_tokens=True).strip()
    print(reply)
    history.append({"role": "assistant", "content": reply})
