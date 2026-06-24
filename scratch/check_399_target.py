import json

log_path = r"C:\Users\ondrej.bronec\.gemini\antigravity\brain\f04316b0-fd17-4e7f-9eb5-27ac3285b710\.system_generated\logs\transcript_full.jsonl"

with open(log_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            step = json.loads(line)
            if step.get("step_index") == 399:
                tc = step.get("tool_calls", [])[0]
                target_str = tc["args"]["TargetContent"]
                replacement_str = tc["args"]["ReplacementContent"]
                with open("scratch/target_399.txt", 'w', encoding='utf-8') as outf:
                    outf.write(target_str)
                with open("scratch/replacement_399.txt", 'w', encoding='utf-8') as outf2:
                    outf2.write(replacement_str)
                print(f"Dumped step 399 target/replacement (len target={len(target_str)}, len replacement={len(replacement_str)})")
        except Exception as e:
            print(f"Error: {e}")
