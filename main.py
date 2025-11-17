import os
from typing import List, Optional, Any, Dict
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Property as PropertySchema, Lead as LeadSchema, Service as ServiceSchema

app = FastAPI(title="Luxury Real Estate & Construction API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class UpdateStatus(BaseModel):
    status: str


def serialize_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    if not doc:
        return doc
    d = dict(doc)
    if "_id" in d:
        d["_id"] = str(d["_id"])
    return d


@app.get("/")
def root():
    return {"name": "Luxury Real Estate & Construction API", "status": "ok"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": "❌ Not Set",
        "database_name": "❌ Not Set",
        "connection_status": "Not Connected",
        "collections": [],
    }
    try:
        if db is not None:
            response["database"] = "✅ Connected & Working"
            response["database_url"] = "✅ Set"
            response["database_name"] = getattr(db, "name", "✅ Connected")
            response["connection_status"] = "Connected"
            response["collections"] = db.list_collection_names()[:10]
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:120]}"
    return response


# ----------------------- Properties -----------------------
@app.get("/api/properties")
def list_properties(
    location: Optional[str] = None,
    type: Optional[str] = None,
    status: Optional[str] = None,
    min_price: Optional[float] = Query(None, alias="price_min"),
    max_price: Optional[float] = Query(None, alias="price_max"),
    bedrooms: Optional[int] = None,
    bathrooms: Optional[float] = None,
    featured: Optional[bool] = None,
    limit: int = 50,
):
    if db is None:
        return []
    f: Dict[str, Any] = {}
    if location:
        f["$or"] = [
            {"location": {"$regex": location, "$options": "i"}},
            {"city": {"$regex": location, "$options": "i"}},
            {"state": {"$regex": location, "$options": "i"}},
        ]
    if type:
        f["type"] = type
    if status:
        f["status"] = status
    if min_price is not None or max_price is not None:
        price_filter: Dict[str, Any] = {}
        if min_price is not None:
            price_filter["$gte"] = float(min_price)
        if max_price is not None:
            price_filter["$lte"] = float(max_price)
        f["price"] = price_filter
    if bedrooms is not None:
        f["bedrooms"] = {"$gte": bedrooms}
    if bathrooms is not None:
        f["bathrooms"] = {"$gte": bathrooms}
    if featured is not None:
        f["featured"] = featured

    items = db["property"].find(f).limit(int(limit))
    return [serialize_doc(x) for x in items]


@app.get("/api/properties/{identifier}")
def get_property(identifier: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    f: Dict[str, Any] = {"$or": [{"slug": identifier}]}
    # try by id
    if ObjectId.is_valid(identifier):
        f["$or"].append({"_id": ObjectId(identifier)})
    doc = db["property"].find_one(f)
    if not doc:
        raise HTTPException(status_code=404, detail="Property not found")
    return serialize_doc(doc)


@app.post("/api/properties")
def create_property(payload: PropertySchema):
    _id = create_document("property", payload)
    return {"_id": _id}


@app.put("/api/properties/{prop_id}")
def update_property(prop_id: str, payload: PropertySchema):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    if not ObjectId.is_valid(prop_id):
        raise HTTPException(status_code=400, detail="Invalid id")
    data = payload.model_dump()
    data["updated_at"] = __import__("datetime").datetime.utcnow()
    res = db["property"].update_one({"_id": ObjectId(prop_id)}, {"$set": data})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Property not found")
    return {"updated": True}


@app.patch("/api/properties/{prop_id}/status")
def update_property_status(prop_id: str, status: UpdateStatus):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    if not ObjectId.is_valid(prop_id):
        raise HTTPException(status_code=400, detail="Invalid id")
    res = db["property"].update_one(
        {"_id": ObjectId(prop_id)}, {"$set": {"status": status.status}}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Property not found")
    return {"updated": True}


# ----------------------- Services -----------------------
@app.get("/api/services")
def list_services(limit: int = 50):
    if db is None:
        return []
    items = db["service"].find({}).limit(int(limit))
    return [serialize_doc(x) for x in items]


@app.post("/api/services")
def create_service(payload: ServiceSchema):
    _id = create_document("service", payload)
    return {"_id": _id}


# ----------------------- Leads -----------------------
@app.post("/api/leads")
def create_lead(payload: LeadSchema):
    # Basic scoring heuristic
    score = 0
    if payload.email:
        score += 10
    if payload.phone and len(payload.phone) >= 10:
        score += 20
    if payload.message and len(payload.message) > 80:
        score += 10
    data = payload.model_dump()
    data["score"] = score
    lead_id = create_document("lead", data)

    # CRM integration (HubSpot optional)
    try:
        hubspot_token = os.getenv("HUBSPOT_API_KEY")
        if hubspot_token:
            import requests

            hs_payload = {
                "properties": {
                    "email": payload.email or "",
                    "firstname": payload.name,
                    "phone": payload.phone or "",
                    "message": payload.message or "",
                    "tags": ",".join(payload.tags or []),
                    "source": payload.source or "website",
                    "property_id": payload.property_id or "",
                }
            }
            requests.post(
                "https://api.hubapi.com/crm/v3/objects/contacts",
                headers={"Authorization": f"Bearer {hubspot_token}", "Content-Type": "application/json"},
                json=hs_payload,
                timeout=6,
            )
    except Exception:
        pass

    return {"_id": lead_id, "score": score}


@app.get("/api/export/crm")
def export_properties_to_crm(limit: int = 100):
    # Dummy endpoint to demonstrate export action
    items = get_documents("property", {}, limit)
    return {"exported": len(items)}


# ----------------------- SEO helper -----------------------
@app.get("/api/seo/{kind}/{slug}")
def get_seo(kind: str, slug: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    coll = kind.lower()
    doc = db[coll].find_one({"slug": slug})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    return serialize_doc(doc.get("seo", {}))


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
