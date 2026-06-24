import json

log_path = r"C:\Users\ondrej.bronec\.gemini\antigravity\brain\f04316b0-fd17-4e7f-9eb5-27ac3285b710\.system_generated\logs\transcript_full.jsonl"

steps_to_check = {180, 186}

with open(log_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            step = json.loads(line)
            step_idx = step.get("step_index", 0)
            if step_idx in steps_to_check:
                tc = step.get("tool_calls", [])[0]
                args = tc["args"]
                print(f"Step {step_idx} target length: {len(args.get('TargetContent'))}")
                print(f"Target:\n{args.get('TargetContent')}")
                print(f"Replacement:\n{args.get('ReplacementContent')}")
                print("=" * 60)
        except Exception as e:
            pass
