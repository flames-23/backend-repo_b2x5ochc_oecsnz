import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import User, Ride, DriverStatus

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helpers
class IdResponse(BaseModel):
    id: str


def to_str_id(doc):
    if doc is None:
        return None
    d = {**doc}
    if "_id" in d and isinstance(d["_id"], ObjectId):
        d["id"] = str(d.pop("_id"))
    return d


@app.get("/")
def read_root():
    return {"message": "Bike Taxi API running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    import os as _os
    response["database_url"] = "✅ Set" if _os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if _os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


# Auth-lite endpoints (no real auth, just demo users)
@app.post("/api/users", response_model=IdResponse)
def create_user(user: User):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    user_id = create_document("user", user)
    return {"id": user_id}


@app.get("/api/drivers")
def list_available_drivers() -> List[dict]:
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    drivers = db["user"].find({"role": "driver", "is_active": True})
    result = []
    for d in drivers:
        profile = to_str_id(d)
        status = db["driverstatus"].find_one({"user_id": profile["id"]})
        profile["status"] = status and {k: v for k, v in status.items() if k != "_id"}
        result.append(profile)
    return result


class RideRequest(BaseModel):
    rider_id: str
    pickup: str
    dropoff: str


@app.post("/api/rides", response_model=IdResponse)
def request_ride(req: RideRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    ride = Ride(
        rider_id=req.rider_id,
        pickup=req.pickup,
        dropoff=req.dropoff,
        status="requested",
    )
    ride_id = create_document("ride", ride)
    return {"id": ride_id}


@app.get("/api/rides")
def list_rides(rider_id: Optional[str] = None):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    filter_q = {}
    if rider_id:
        filter_q["rider_id"] = rider_id
    rides = db["ride"].find(filter_q).sort("created_at", -1).limit(20)
    return [to_str_id(r) for r in rides]


class AssignDriver(BaseModel):
    driver_id: str


@app.post("/api/rides/{ride_id}/assign")
def assign_driver(ride_id: str, body: AssignDriver):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        oid = ObjectId(ride_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ride id")

    res = db["ride"].update_one({"_id": oid}, {"$set": {"driver_id": body.driver_id, "status": "accepted", "updated_at": __import__('datetime').datetime.utcnow()}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Ride not found")
    return {"ok": True}


class UpdateRideStatus(BaseModel):
    status: str


@app.post("/api/rides/{ride_id}/status")
def update_ride_status(ride_id: str, body: UpdateRideStatus):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        oid = ObjectId(ride_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ride id")
    if body.status not in ["requested", "accepted", "picked_up", "completed", "cancelled"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    res = db["ride"].update_one({"_id": oid}, {"$set": {"status": body.status, "updated_at": __import__('datetime').datetime.utcnow()}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Ride not found")
    return {"ok": True}


class UpdateDriverStatus(BaseModel):
    user_id: str
    is_available: bool
    lat: Optional[float] = None
    lng: Optional[float] = None


@app.post("/api/driver/status")
def update_driver_status(body: UpdateDriverStatus):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    existing = db["driverstatus"].find_one({"user_id": body.user_id})
    data = body.model_dump()
    data.pop("user_id")
    if existing:
        db["driverstatus"].update_one({"_id": existing["_id"]}, {"$set": {**data, "updated_at": __import__('datetime').datetime.utcnow()}})
    else:
        create_document("driverstatus", {"user_id": body.user_id, **data})
    return {"ok": True}


# Basic schema endpoint to help tooling introspect
@app.get("/schema")
def get_schema():
    return {
        "user": {"fields": list(User.model_fields.keys())},
        "ride": {"fields": list(Ride.model_fields.keys())},
        "driverstatus": {"fields": list(DriverStatus.model_fields.keys())},
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
