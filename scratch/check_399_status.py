import json

log_path = r"C:\Users\ondrej.bronec\.gemini\antigravity\brain\f04316b0-fd17-4e7f-9eb5-27ac3285b710\.system_generated\logs\transcript_full.jsonl"

with open(log_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            step = json.loads(line)
            if step.get("step_index") == 400: # The tool output step for step 399
                print("Step 400 (Output of step 399 tool call):")
                print(f"Status: {step.get('status')}")
                print(f"Content: {step.get('content')[:300]}")
        except Exception as e:
            pass
