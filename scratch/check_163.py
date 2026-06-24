import json

log_path = r"C:\Users\ondrej.bronec\.gemini\antigravity\brain\f04316b0-fd17-4e7f-9eb5-27ac3285b710\.system_generated\logs\transcript_full.jsonl"

with open(log_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            step = json.loads(line)
            if step.get("step_index") == 163:
                tc = step.get("tool_calls", [])[0]
                args = tc["args"]
                print(f"Step 163 replacement size={len(args.get('ReplacementContent'))}")
                print("ReplacementContent first 200:")
                print(repr(args.get('ReplacementContent')[:200]))
                print("Does 'en:' exist in replacement?")
                print("en:" in args.get('ReplacementContent'))
                print("en : " in args.get('ReplacementContent'))
        except Exception as e:
            pass
