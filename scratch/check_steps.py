import json

log_path = r"C:\Users\ondrej.bronec\.gemini\antigravity\brain\f04316b0-fd17-4e7f-9eb5-27ac3285b710\.system_generated\logs\transcript_full.jsonl"

with open(log_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            step = json.loads(line)
            step_idx = step.get("step_index", 0)
            if 260 <= step_idx <= 400:
                tool_calls = step.get("tool_calls", [])
                if tool_calls:
                    print(f"Step {step_idx}: {[tc.get('name') for tc in tool_calls]} - source {step.get('source')}")
        except Exception as e:
            pass
