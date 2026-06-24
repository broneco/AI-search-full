import json

log_path = r"C:\Users\ondrej.bronec\.gemini\antigravity\brain\f04316b0-fd17-4e7f-9eb5-27ac3285b710\.system_generated\logs\transcript_full.jsonl"

with open(log_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            step = json.loads(line)
            step_idx = step.get("step_index", 0)
            tool_calls = step.get("tool_calls", [])
            for tc in tool_calls:
                name = tc.get("name")
                args = tc.get("args", {})
                content = str(args)
                if "configurationTitle" in content and "AI Search Settings" in content:
                    # Let's see if this is cs or en block
                    print(f"Step {step_idx}: {name} containing both configurationTitle and AI Search Settings")
        except Exception as e:
            pass
