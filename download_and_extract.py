import os
import requests
from pdf_extractor import extract_pdf_text

def download_file(url: str, local_filename: str):
    """
    Downloads a file from a URL to a local path.
    """
    print(f"Downloading {url} to {local_filename}...")
    headers = {'User-Agent': 'Mozilla/5.0'}
    with requests.get(url, stream=True, headers=headers) as r:
        r.raise_for_status()
        with open(local_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    print("Download complete.")
    return local_filename

def main():
    # A sample PDF URL for testing
    sample_pdf_url = "https://raw.githubusercontent.com/mozilla/pdf.js/master/test/pdfs/tracemonkey.pdf"
    test_dir = "test_data"
    
    os.makedirs(test_dir, exist_ok=True)
    local_path = os.path.join(test_dir, "dummy_test.pdf")
    
    try:
        # 1. Download the PDF
        download_file(sample_pdf_url, local_path)
        
        # 2. Run the extraction
        print(f"\n--- Starting Extraction for {local_path} ---")
        extracted_text = extract_pdf_text(local_path)
        
        # 3. Save the results
        out_file = os.path.join(test_dir, "extracted_output.txt")
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(extracted_text)
            
        print(f"\n--- Extraction Result saved to {out_file} ---\n")
        print("\n-------------------------\n")
        
        print("Test completed successfully.")
        
    except Exception as e:
        print(f"An error occurred during testing: {e}")
        
    finally:
        # Optional: clean up the downloaded file
        if os.path.exists(local_path):
            os.remove(local_path)
            print(f"Cleaned up temporary file: {local_path}")

if __name__ == "__main__":
    main()
