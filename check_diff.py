import os
import fitz

def normalize_text(text: str) -> str:
    text = text.lower()
    return "".join(c for c in text if c.isalnum() and ord(c) < 128)

def check_diff():
    pdf_path = os.path.abspath("data/R_399_registr_smluv.pdf")
    doc = fitz.open(pdf_path)
    page = doc[0]
    
    snippet = 'ní těchto smluv a o registru smluv (zákon o registru smluv) , ve znění pozdějších předpisů (dále jen „ZRS“), jenž nabyl účinnosti dnem 1. 7. 2016. I. Předmět úpravy 1. Toto opatření stanovuje pravidla pro jednotný způsob uveřejňování smluv, které uzavírá JU na úrovni rektorátu a součástí. 2. Účelem opatření je definovat způsob povinné evidence smluv na JU a zajistit plnění povinností dle ZRS. II. Vymezení pojmů Pro účely tohoto opatření se stanovují definice následujících pojmů: Smlouva: Jakákoli p ísemně uzavřená smlouva bez ohledu na výši h odnoty předmětu plnění a skutečnost, které právo je pro danou smlouvu rozhodné dle mezinárodního práva soukromého. Za smlouvu se považuje rovněž písemná oboustranně odsouhlasená objednávka (ať již vystavená JU či druhou smluvní stranou).'
    
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
