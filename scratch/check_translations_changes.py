import json

log_path = r"C:\Users\ondrej.bronec\.gemini\antigravity\brain\f04316b0-fd17-4e7f-9eb5-27ac3285b710\.system_generated\logs\transcript_full.jsonl"

with open(log_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            step = json.loads(line)
            step_idx = step.get("step_index", 0)
            if step_idx < 399:
                tool_calls = step.get("tool_calls", [])
                for tc in tool_calls:
                    name = tc.get("name")
                    args = tc.get("args", {})
                    target = args.get("TargetFile") or args.get("AbsolutePath")
                    if target and "page.tsx" in target:
                        tc_target = args.get('TargetContent', '')
                        # Check if any key from TRANSLATIONS is in target content
                        if "title:" in tc_target or "subtitle:" in tc_target or "TRANSLATIONS" in tc_target:
                            print(f"Step {step_idx}: {name} modified TRANSLATIONS (target len {len(tc_target)})")
        except Exception as e:
            pass
