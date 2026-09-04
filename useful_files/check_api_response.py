"""
Quick API Response Inspector
============================
Checks the JSON response from the external portal API or spins up a local mock server.

Usage:
  1. Test Live External API:
     python useful_files/check_api_response.py --url "https://api.externalportal.gov.in/api/v1/sync/kit-tracker" --key "YOUR_API_KEY"

  2. Test with Local Mock API (if external team hasn't deployed yet):
     python useful_files/check_api_response.py --mock
"""
import sys
import json
import argparse
import requests

def inspect_live_api(url: str, api_key: str):
    print(f"\n[*] Connecting to: {url}")
    masked = ('*' * (len(api_key)-4) + api_key[-4:]) if len(api_key) > 4 else '***'
    print(f"[*] Using Token: {masked}\n")
    
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}" if not api_key.startswith("Bearer ") else api_key,
        "X-API-Key": api_key
    }
    
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        response = requests.get(url, headers=headers, timeout=15, verify=False)
        print(f"Status Code: {response.status_code} {response.reason}")
        
        try:
            data = response.json()
            print("\n--- JSON RESPONSE PREVIEW ---")
            preview_keys = list(data.keys())
            print(f"Top-level keys in response: {preview_keys}")
            
            for key in ["operators", "kits_details", "onboard_details"]:
                if key in data:
                    print(f"  - {key}: {len(data[key])} records")
            
            print("\nSample records:")
            if "operators" in data and data["operators"]:
                print(f"  First operator: {data['operators'][0]}")
            if "kits_details" in data and data["kits_details"]:
                print(f"  First kit: {data['kits_details'][0]}")
            if "onboard_details" in data and data["onboard_details"]:
                print(f"  First onboarding: {data['onboard_details'][0]}")
                
        except json.JSONDecodeError:
            print("Response is not JSON! Raw text preview:")
            print(response.text[:500])
            
    except requests.exceptions.RequestException as e:
        print(f"Connection Failed: {e}")

def run_mock_server(port: int = 8085):
    from http.server import HTTPServer, BaseHTTPRequestHandler
    
    sample_response = {
        "success": True,
        "timestamp": "2026-09-03T10:00:00Z",
        "total_records": 2,
        "page": 1,
        "page_size": 200,
        "data": [
            {
                "station_id": "ST_49001",
                "district": "Raipur",
                "machine_id": "MCH_88219",
                "laptop_serial_no": "LPT-77123",
                "laptop_name": "HP ProBook 440",
                "kit_slot": "Fixed ASK",
                "block": "Dharsiwa",
                "locality": "Civil Lines",
                "ask_address": "Near Collectorate Office, Raipur",
                "station_status": "Active",
                "station_id_allotted_date": "2026-01-15",
                "operator": {
                    "operator_code": "OP_98765",
                    "name": "Ramesh Verma",
                    "mobile": "9826012345",
                    "status": "Active",
                    "security_deposit_status": "Received",
                    "security_deposit_date": "2026-01-18",
                    "inactive_reason": None,
                    "inactive_date": None
                },
                "workflow": {
                    "l1_status": "Done",
                    "l1_done_date": "2026-02-01",
                    "l2_status": "Pending",
                    "l2_done_date": None,
                    "onboarding_status": "Pending",
                    "onboard_date": None,
                    "visit_status": "Completed",
                    "visit_date": "2026-02-10",
                    "permitted_18_plus": "Yes",
                    "kit_working_status": "Working",
                    "remark": "Awaiting L2 approval"
                }
            }
        ]
    }

    class MockHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(sample_response, indent=2).encode("utf-8"))
            
        def log_message(self, format, *args):
            print(f"[Mock Server] {self.address_string()} - {args[0]}")

    server = HTTPServer(("127.0.0.1", port), MockHandler)
    print(f"\n[+] Mock Server started at: http://127.0.0.1:{port}/api/v1/sync/kit-tracker")
    print("You can view the JSON in your browser or curl it now.")
    print("Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nMock server stopped.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="API Response Inspector")
    parser.add_argument("--url", help="API Endpoint URL")
    parser.add_argument("--key", default="", help="X-API-Key header")
    parser.add_argument("--mock", action="store_true", help="Spin up local mock API server")
    parser.add_argument("--port", type=int, default=8085, help="Port for mock server")
    args = parser.parse_args()

    if args.mock:
        run_mock_server(port=args.port)
    elif args.url:
        inspect_live_api(args.url, args.key)
    else:
        print("Please provide --url and --key to test live API, or --mock to run local mock server.")
        print("Example: python useful_files/check_api_response.py --mock")
