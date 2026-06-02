import httpx, json
r = httpx.get('http://127.0.0.1:8001/stores/STORE_BLR_002/metrics')
print(r.status_code)
print(json.dumps(r.json(), indent=2))
