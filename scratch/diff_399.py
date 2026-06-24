with open("scratch/target_399.txt", "r", encoding="utf-8") as f:
    target = f.read()

with open("scratch/page_at_398.tsx", "r", encoding="utf-8") as f:
    content = f.read()

idx = content.find("const TRANSLATIONS = {")
if idx == -1:
    print("Could not find TRANSLATIONS in page_at_398.tsx")
else:
    print(f"Found TRANSLATIONS in page_at_398.tsx at index {idx}")
    # Let's see if target matches from there
    matched = content[idx:idx+len(target)]
    print(f"Length of target: {len(target)}")
    print(f"Length of matched from content: {len(matched)}")
    
    # Compare line by line
    target_lines = target.splitlines()
    matched_lines = content[idx:].splitlines()[:len(target_lines)]
    
    for i, (t_line, m_line) in enumerate(zip(target_lines, matched_lines)):
        if t_line != m_line:
            print(f"Line {i+1} mismatch:")
            print(f"  Target:  {repr(t_line)}")
            print(f"  Content: {repr(m_line)}")
            break
    else:
        print("All lines matched!")
