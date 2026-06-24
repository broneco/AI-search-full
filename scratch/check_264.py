import json

log_path = r"C:\Users\ondrej.bronec\.gemini\antigravity\brain\f04316b0-fd17-4e7f-9eb5-27ac3285b710\.system_generated\logs\transcript_full.jsonl"

with open(log_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            step = json.loads(line)
            if step.get("step_index") == 264:
                tc = step.get("tool_calls", [])[0]
                args = tc["args"]
                print(f"Step 264: target size={len(args.get('TargetContent'))}, replacement size={len(args.get('ReplacementContent'))}")
                print("TargetContent first 100:")
                print(repr(args.get('TargetContent')[:100]))
                print("ReplacementContent first 100:")
                print(repr(args.get('ReplacementContent')[:100]))
        except Exception as e:
            pass
