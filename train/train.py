"""QLoRA fine-tune of Qwen3 on sft_train.jsonl. Runs on a single 16 GB GPU (RTX 4080 Super).

    python train/train.py --data data/processed --out outputs/engram-v1
"""
from __future__ import annotations

import argparse

from unsloth import FastLanguageModel  # must be imported before transformers/trl
from unsloth.chat_templates import get_chat_template, train_on_responses_only

from datasets import load_dataset
from trl import SFTConfig, SFTTrainer

p = argparse.ArgumentParser()
p.add_argument("--data", default="data/processed")
p.add_argument("--out", default="outputs/engram")
p.add_argument("--model", default="unsloth/Qwen3-8B", help="unsloth/Qwen3-4B for fast iteration, unsloth/Qwen3-14B to max out 16 GB")
p.add_argument("--max-seq", type=int, default=4096)
p.add_argument("--epochs", type=float, default=2)
p.add_argument("--lr", type=float, default=1e-4)
p.add_argument("--rank", type=int, default=32)
p.add_argument("--batch", type=int, default=2)
p.add_argument("--grad-accum", type=int, default=8)
p.add_argument("--gguf", default="q4_k_m", help="quantization for the exported GGUF ('' to skip)")
args = p.parse_args()

model, tokenizer = FastLanguageModel.from_pretrained(args.model, max_seq_length=args.max_seq, load_in_4bit=True)
model = FastLanguageModel.get_peft_model(
    model, r=args.rank, lora_alpha=args.rank, lora_dropout=0,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    use_gradient_checkpointing="unsloth", random_state=0,
)
tokenizer = get_chat_template(tokenizer, chat_template="qwen3")


def render(batch):
    return {"text": [tokenizer.apply_chat_template(m, tokenize=False, enable_thinking=False)
                     for m in batch["messages"]]}


files = {"train": f"{args.data}/sft_train.jsonl", "val": f"{args.data}/sft_val.jsonl"}
ds = load_dataset("json", data_files=files).map(render, batched=True, remove_columns=["messages", "source"])

trainer = SFTTrainer(
    model=model, tokenizer=tokenizer, train_dataset=ds["train"], eval_dataset=ds["val"],
    args=SFTConfig(
        dataset_text_field="text", max_seq_length=args.max_seq, packing=False,
        per_device_train_batch_size=args.batch, gradient_accumulation_steps=args.grad_accum,
        num_train_epochs=args.epochs, learning_rate=args.lr, lr_scheduler_type="cosine", warmup_ratio=0.03,
        optim="adamw_8bit", weight_decay=0.01, bf16=True, logging_steps=10,
        eval_strategy="steps", eval_steps=200, save_steps=500, save_total_limit=3,
        output_dir=f"{args.out}/checkpoints", report_to="none", seed=0,
    ),
)
# Loss only on my replies, never on other people's messages
trainer = train_on_responses_only(trainer, instruction_part="<|im_start|>user\n",
                                  response_part="<|im_start|>assistant\n")
trainer.train()

model.save_pretrained(f"{args.out}/lora")
tokenizer.save_pretrained(f"{args.out}/lora")
if args.gguf:
    model.save_pretrained_gguf(f"{args.out}/gguf", tokenizer, quantization_method=args.gguf)
print(f"done -> {args.out}/lora" + (f", {args.out}/gguf" if args.gguf else ""))
