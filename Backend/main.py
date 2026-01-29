from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from jose import jwt, JWTError
from datetime import datetime, timedelta
import random
import os
import json

import firebase_admin
from firebase_admin import credentials, firestore

# ===================== CONFIG =====================
JWT_SECRET = "women-safety-secret"
JWT_ALGO = "HS256"
JWT_EXPIRE_MINUTES = 120

# ===================== APP =====================
app = FastAPI(title="Women Safety Cloud Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===================== FIREBASE INIT (FINAL FIX) =====================
# Works BOTH locally (file) and on Render (env variable)

if not firebase_admin._apps:
    if os.path.exists("firebase-key.json"):
        # Local development
        cred = credentials.Certificate("firebase-key.json")
    else:
        # Cloud / Render
        firebase_key = json.loads(os.environ["FIREBASE_KEY"])
        cred = credentials.Certificate(firebase_key)

    firebase_admin.initialize_app(cred)

db = firestore.client()

# ===================== MODELS =====================
class OTPRequest(BaseModel):
    phone: str

class OTPVerify(BaseModel):
    phone: str
    otp: str

class SetupRequest(BaseModel):
    name: str
    contacts: list

class LocationUpdate(BaseModel):
    lat: float
    lon: float

class SOSRequest(BaseModel):
    reason: str
    score: int

# ===================== AUTH =====================
otp_store = {}  # DEMO ONLY (in-memory)

def create_token(phone: str):
    payload = {
        "sub": phone,
        "exp": datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

def get_current_user(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")

    token = authorization.split(" ")[1]

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        return payload["sub"]
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

# ===================== ROUTES =====================

@app.get("/")
def health():
    return {"status": "Backend running"}

# -------- OTP --------
@app.post("/auth/send-otp")
def send_otp(req: OTPRequest):
    otp = str(random.randint(100000, 999999))
    otp_store[req.phone] = otp

    print(f"[DEMO OTP] {req.phone} -> {otp}")

    # Demo response (for college / testing)
    return {
        "message": "OTP generated (demo mode)",
        "otp": otp
    }

@app.post("/auth/verify-otp")
def verify_otp(req: OTPVerify):
    if otp_store.get(req.phone) != req.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    otp_store.pop(req.phone)
    token = create_token(req.phone)
    return {"token": token}

# -------- USER SETUP --------
@app.post("/user/setup")
def setup_user(req: SetupRequest, phone: str = Depends(get_current_user)):
    db.collection("users").document(phone).set({
        "name": req.name,
        "contacts": req.contacts,
        "created": firestore.SERVER_TIMESTAMP
    })
    return {"message": "Profile saved"}

# -------- LOCATION --------
@app.post("/user/location")
def update_location(loc: LocationUpdate, phone: str = Depends(get_current_user)):
    db.collection("locations").document(phone).set({
        "lat": loc.lat,
        "lon": loc.lon,
        "time": firestore.SERVER_TIMESTAMP
    })
    return {"message": "Location updated"}

@app.get("/user/location/{phone}")
def get_location(phone: str):
    doc = db.collection("locations").document(phone).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Location not found")
    return doc.to_dict()

# -------- SOS --------
@app.post("/alert/sos")
def sos(req: SOSRequest, phone: str = Depends(get_current_user)):
    db.collection("alerts").add({
        "phone": phone,
        "reason": req.reason,
        "score": req.score,
        "time": firestore.SERVER_TIMESTAMP
    })
    return {"status": "SOS logged"}
