import os
import fitz

def normalize_text(text: str) -> str:
    text = text.lower()
    return "".join(c for c in text if c.isalnum() and ord(c) < 128)

def check_diff():
    pdf_path = os.path.abspath("data/S-10.160.v100-Podpisový_řád.pdf")
    doc = fitz.open(pdf_path)
    page = doc[1]  # Page 2 contains the introductory text block
    
    snippet = 'Tato pravidla pro podepisování jsou závazná pro všechny pracovníky a útvary společnosti dolphin consulting a.s. (dále jen společnost). Funkce uvedené v těchto pravidlech pro podepisování se vztahují výhradně na pracovníky společnosti, pokud nebude uvedeno jinak.'
    
    norm_snippet = normalize_text(snippet)
    norm_page = normalize_text(page.get_text())
    
    print("Normalized Snippet (first 100 chars):")
    print(norm_snippet[:100])
    
    # Try to find a smaller piece first to see where it succeeds
    words = snippet.split()
    for i in range(1, len(words) + 1):
        sub_snippet = " ".join(words[:i])
        norm_sub = normalize_text(sub_snippet)
        if norm_page.find(norm_sub) == -1:
            print(f"\nFails at word index {i-1}: '{words[i-1]}'")
            print("Sub-snippet up to failure:")
            print(sub_snippet)
            print("\nNormalized sub-snippet up to failure:")
            print(norm_sub)
            break
            
    doc.close()

if __name__ == "__main__":
    check_diff()
