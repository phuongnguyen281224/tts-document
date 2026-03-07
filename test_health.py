import requests
import time

BASE_URL = "http://localhost:8000"

def test_liveness():
    print("--- Testing Liveness Probe ---")
    try:
        response = requests.get(f"{BASE_URL}/health/live")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        assert response.status_code == 200
        print("[SUCCESS] Liveness probe passed.")
    except Exception as e:
        print(f"[ERROR] Liveness probe failed: {e}")

def test_readiness():
    print("\n--- Testing Readiness Probe ---")
    try:
        response = requests.get(f"{BASE_URL}/health/ready")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            print("[SUCCESS] Readiness probe passed. Services are UP.")
        elif response.status_code == 503:
            print("[WARNING] Readiness probe returned 503. Services are DOWN (as expected if testing failure).")
        else:
            print(f"[ERROR] Unexpected status code: {response.status_code}")
    except Exception as e:
        print(f"[ERROR] Readiness probe failed: {e}")

if __name__ == "__main__":
    test_liveness()
    test_readiness()
