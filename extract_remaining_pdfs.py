import pdfplumber
import os

for pdf_name in ['HSS-Form0004-Prescription.pdf', 'HSS-Form0005-Medical Certificate.pdf']:
    print("\n" + "=" * 80)
    print(f"FILE: {pdf_name}")
    print("=" * 80)
    try:
        with pdfplumber.open(os.path.join('health_forms', pdf_name)) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                print(f"\n--- PAGE {page_num} ---")
                print(text)
    except Exception as e:
        print(f"Error: {e}")
