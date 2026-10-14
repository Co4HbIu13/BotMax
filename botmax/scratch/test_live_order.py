import json
import sys
import urllib.request
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "https://anussai.duckdns.org"

print("1. Fetching active raffles...")
req = urllib.request.Request(f"{BASE_URL}/api/raffles")
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode())
    raffles = data.get("raffles", [])
    print(f"Found {len(raffles)} raffles:")
    for r in raffles:
        print(f" - {r['id']}: {r['title']} (Creator: {r.get('creator_name')} | Phone: {r.get('creator_sbp_phone')} | Bank: {r.get('creator_sbp_bank')})")

for target_raffle in raffles:
    req = urllib.request.Request(f"{BASE_URL}/api/raffles/{target_raffle['id']}")
    with urllib.request.urlopen(req) as resp:
        board_data = json.loads(resp.read().decode())
        raffle_obj = board_data.get("raffle", {})
        tickets = raffle_obj.get("tickets", [])
        avail = [t["ticket_number"] for t in tickets if t["status"] == "available"]
        print(f"Raffle {target_raffle['id']}: {len(avail)}/{len(tickets)} available tickets")

    if avail:
        test_ticket = avail[0]
        print(f"\nTesting reservation on #{test_ticket} in {target_raffle['title']}...")
        payload = json.dumps({
            "ticket_numbers": [test_ticket],
            "user_id": 999999,
            "username": "test_buyer",
            "phone": "+79990001122"
        }).encode()
        post_req = urllib.request.Request(
            f"{BASE_URL}/api/raffles/{target_raffle['id']}/reserve",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(post_req) as resp:
            order_data = json.loads(resp.read().decode())
            print("Order ID:", order_data.get("order_id"))
            print("Order Data SBP tbank_url:", order_data.get("sbp", {}).get("tbank_url"))
            print("Recipient:", order_data.get("recipient"))
            print("QR Data URL length:", len(order_data.get("sbp", {}).get("qr_data_url", "")))

        order_id = order_data.get("order_id")
        if order_id:
            print(f"Cancelling test reservation {order_id}...")
            cancel_payload = json.dumps({"user_id": 999999}).encode()
            cancel_req = urllib.request.Request(
                f"{BASE_URL}/api/orders/{order_id}/cancel",
                data=cancel_payload,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(cancel_req) as resp:
                print("Cancel Result:", json.loads(resp.read().decode()))
        break
