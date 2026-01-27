import pdfplumber
import os

pdf_path = os.path.join('health_forms', 'HSS-Form0001-HealthProfileForm.pdf')

try:
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text()
            print(f"\n{'='*80}")
            print(f"PAGE {page_num}")
            print('='*80)
            print(text)
except Exception as e:
    print(f"Error: {e}")
    print(f"Current directory: {os.getcwd()}")
    print(f"Files in health_forms: {os.listdir('health_forms') if os.path.exists('health_forms') else 'Directory not found'}")
