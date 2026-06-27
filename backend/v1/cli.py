import urllib.request
import urllib.parse
import json
import sys

def main():
    print("========================================")
    print("Hermes V2 - Testing CLI")
    print("========================================")
    
    question = input("\nEnter your UPSC question: ")
    if not question:
        return
        
    print("\n[!] Sending to LangGraph Orchestrator (via FastAPI)...")
    print("[!] This will query Qdrant (Old DB) and generate via OpenRouter.")
    
    url = f"http://localhost:8000/api/answer?question={urllib.parse.quote(question)}&session_id=cli-test"
    req = urllib.request.Request(url, method='POST')
    
    try:
        res = urllib.request.urlopen(req)
        data = json.loads(res.read().decode())
        
        print("\n--- RESULTS ---")
        print(f"Domain: {data.get('domain')}")
        print(f"Revisions: {data.get('revisions')}")
        print("\nFinal Answer:\n")
        print(data.get('answer'))
        
    except urllib.error.HTTPError as e:
        print(f"\n[ERROR] HTTP {e.code}: {e.reason}")
        error_body = e.read().decode()
        print(f"Details: {error_body}")
        print("\n[HINT] Ensure OPENROUTER_API_KEY is properly set in hermes_v2/backend/.env")

if __name__ == "__main__":
    main()
