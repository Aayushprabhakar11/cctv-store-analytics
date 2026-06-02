import json
import httpx

def main():
    with open('data/generated_events.jsonl') as f:
        lines = [json.loads(l) for l in f]
    resp = httpx.post('http://127.0.0.1:8000/events/ingest', json={'events': lines[:5]})
    print(resp.status_code)
    print(resp.text)

if __name__ == '__main__':
    main()
