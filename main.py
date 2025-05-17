from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from apify_client import ApifyClient
import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Apify setup
APIFY_TOKEN = "apify_api_YUbNNMIypt7hANBwxdhsjVNYFFxEER0nDhqe"
APIFY_ACTOR_ID = "Us34x9p7VgjCz99H6"
client = ApifyClient(APIFY_TOKEN)

# Plan limits
plan_limits = {
    "starter": 3,
    "pro": 10,
    "power": 20
}

class FacebookSearchRequest(BaseModel):
    category: str
    location: str
    userId: str
    plan: str
    searchesThisWeek: dict

@app.post("/find-facebook-pages")
async def find_facebook_pages(payload: FacebookSearchRequest):
    print("🔍 Incoming Facebook search payload:", payload.dict())

    limits = plan_limits.get(payload.plan)
    if limits is None:
        raise HTTPException(status_code=400, detail="Invalid plan")

    now = datetime.datetime.utcnow()
    try:
        week_start = datetime.datetime.fromisoformat(payload.searchesThisWeek["weekStart"].replace("Z", ""))
    except Exception:
        payload.searchesThisWeek["weekStart"] = now.isoformat() + "Z"
        payload.searchesThisWeek["basic"] = 0

    if (now - week_start).days >= 7:
        payload.searchesThisWeek["basic"] = 0
        payload.searchesThisWeek["weekStart"] = now.isoformat() + "Z"

    if payload.searchesThisWeek["basic"] >= limits:
        raise HTTPException(status_code=403, detail="Search limit reached for your plan")

    run_input = {
        "categories": [payload.category.strip()],
        "locations": [payload.location.strip()],
        "resultsLimit": limits
    }

    try:
        print("🚀 Running Apify Facebook scraper with:", run_input)
        run = client.actor(APIFY_ACTOR_ID).call(run_input=run_input)
        dataset_id = run["defaultDatasetId"]

        items = list(client.dataset(dataset_id).iterate_items())
        print(f"✅ Retrieved {len(items)} Facebook pages")

        payload.searchesThisWeek["basic"] += 1

        return {
            "results": items,
            "searchesUsed": payload.searchesThisWeek
        }
    except Exception as e:
        print("❌ Apify scraper failed:", str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch Facebook page data")