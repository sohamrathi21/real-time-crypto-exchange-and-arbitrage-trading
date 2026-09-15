import argparse
import asyncio
import json
from pathlib import Path
import httpx


async def record_session(url, seconds, output):
    frames = []
    async with httpx.AsyncClient(base_url=url, timeout=10) as client:
        for _ in range(seconds):
            markets = (await client.get("/markets")).json()
            chosen = [
                m for m in markets if m["symbol"] in ["BTC/USDT", "ETH/USDT", "ETH/BTC"]
            ]
            response = await asyncio.gather(
                *(
                    client.get("/orderbooks/" + m["exchange"] + "/" + m["symbol"])
                    for m in chosen
                )
            )
            frames.append([r.json() for r in response if r.status_code == 200])
            await asyncio.sleep(1)
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps({"frames": frames}, indent=2))
    print(f"Recorded {len(frames)} actual observed frames to {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--seconds", type=int, default=30)
    parser.add_argument("--output", default="artifacts/session.json")
    args = parser.parse_args()
    asyncio.run(record_session(args.url, args.seconds, args.output))
