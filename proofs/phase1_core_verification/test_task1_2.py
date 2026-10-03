import urllib.request
import json
import subprocess

facts = [
    "I love eating spicy tacos from the food truck downtown.",
    "My favorite coding language is Python.",
    "I want to visit Tokyo, Japan next year for a vacation.",
    "I am highly allergic to peanuts.",
    "My favorite color is dark blue.",
    "I usually wake up at 7 AM every morning.",
    "I have a golden retriever named Max.",
    "I prefer working on backend architecture instead of frontend.",
    "I drive a silver Honda Civic.",
    "I absolutely hate drinking coffee."
]

print('=== 4. INGESTION RAW REQUESTS/RESPONSES ===')
for f in facts:
    req = {
        'tenant_id': 'user_123',
        'agent_id': 'agent_001',
        'session_id': 'sess_999',
        'messages': [{'role': 'user', 'content': f}]
    }
    print(f'RAW REQUEST: {json.dumps(req)}')
    req_bytes = json.dumps(req).encode('utf-8')
    request = urllib.request.Request('http://localhost:8000/v1/memories/ingest', data=req_bytes, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request) as response:
            res_text = response.read().decode('utf-8')
            print(f'RAW RESPONSE ({response.status}): {res_text}')
    except Exception as e:
        print(f'ERROR: {e}')
    print('---')

print('\n=== 5. LIVE COUNT ===')
count_cmd = 'docker exec -i memory_engine_db psql -U user -d memory_engine -t -c "SELECT COUNT(*) FROM memories WHERE temporal_state = \'ACTIVE\';"'
try:
    count_out = subprocess.check_output(count_cmd, shell=True).decode().strip()
    print(f'COUNT: {count_out}')
except Exception as e:
    print(f"Error running count: {e}")

print('\n=== 6. SEARCH QUERIES ===')
search_req = {
    'tenant_id': 'user_123',
    'agent_id': 'agent_001',
    'query': 'What food does the user like?'
}
print(f'RAW REQUEST: {json.dumps(search_req)}')
search_bytes = json.dumps(search_req).encode('utf-8')
request = urllib.request.Request('http://localhost:8000/v1/memories/search', data=search_bytes, headers={'Content-Type': 'application/json'})
try:
    with urllib.request.urlopen(request) as response:
        res_text = response.read().decode('utf-8')
        print(f'RAW RESPONSE ({response.status}): {json.dumps(json.loads(res_text), indent=2)}')
except Exception as e:
    print(f'ERROR: {e}')
