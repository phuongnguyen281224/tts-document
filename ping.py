import requests
import time

def test():
    try:
        r = requests.post('http://localhost:8000/upload-pdf/', files={'file': ('ping.pdf', b'ping')})
        data = r.json()
        print('Started:', data)
        task_id = data['task_id']
        
        print('Status Immed:', requests.get(f'http://localhost:8000/task-status/{task_id}').json())
        
        time.sleep(12)
        
        print('Status Subseq:', requests.get(f'http://localhost:8000/task-status/{task_id}').json())
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test()
