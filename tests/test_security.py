import requests
import os

BASE_URL = "http://localhost:8000"

def test_invalid_content_type():
    print("\n--- Testing Invalid Content-Type (PNG) ---")
    files = {'file': ('test.png', b'not a pdf', 'image/png')}
    response = requests.post(f"{BASE_URL}/upload-pdf/", files=files)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    assert response.status_code == 415

def test_large_file():
    print("\n--- Testing Large File (51MB) ---")
    # Create a 51MB dummy file
    large_file_path = "large_test.pdf"
    with open(large_file_path, "wb") as f:
        f.seek(51 * 1024 * 1024 - 1)
        f.write(b"\0")
    
    try:
        with open(large_file_path, "rb") as f:
            files = {'file': ('large_test.pdf', f, 'application/pdf')}
            response = requests.post(f"{BASE_URL}/upload-pdf/", files=files)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        assert response.status_code == 413
    finally:
        if os.path.exists(large_file_path):
            os.remove(large_file_path)

def test_valid_pdf():
    print("\n--- Testing Valid PDF ---")
    files = {'file': ('small.pdf', b'%PDF-1.4\n%EOF', 'application/pdf')}
    response = requests.post(f"{BASE_URL}/upload-pdf/", files=files)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    assert response.status_code == 200
    assert "task_id" in response.json()

if __name__ == "__main__":
    try:
        test_invalid_content_type()
        test_large_file()
        test_valid_pdf()
        print("\nAll security tests passed!")
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to FastAPI server. Ensure it is running on port 8000.")
    except Exception as e:
        print(f"An error occurred: {e}")
