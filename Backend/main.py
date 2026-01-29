from fastapi import FastAPI, HTTPException, Depends, Header, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from jose import jwt, JWTError
from datetime import datetime, timedelta
import random
import os
import json
import uuid

import firebase_admin
from firebase_admin import credentials, firestore, storage

# ---------------- CONFIG ----------------
JWT_SECRET = "women-safety-secret"
JWT_ALGO = "HS256"
JWT_EXPIRE_MINUTES = 120

# ---------------- APP ----------------
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- FIREBASE INIT ----------------
if not firebase_admin._apps:
    if os.path.exists("firebase-key.json"):
        cred = credentials.Certificate("firebase-key.json")
    else:
        firebase_key = json.loads(os.environ["FIREBASE_KEY"])
        cred = credentials.Certificate(firebase_key)

    firebase_admin.initialize_app(cred, {
        "storageBucket": "women-safety-95702.appspot.com"
    })

db = firestore.client()

# ---------------- MODELS ----------------
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

# ---------------- AUTH ----------------
otp_store = {}

def create_token(phone: str):
    payload = {
        "sub": phone,
        "exp": datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

def get_current_user(authorization: str = Header(...)):
    token = authorization.split(" ")[1]
    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    return payload["sub"]

# ---------------- ROUTES ----------------
@app.get("/")
def health():
    return {"status": "Backend running"}

# ----- OTP -----
@app.post("/auth/send-otp")
def send_otp(req: OTPRequest):
    otp = str(random.randint(100000, 999999))
    otp_store[req.phone] = otp
    print(f"[OTP] {req.phone} -> {otp}")
    return {"otp": otp}

@app.post("/auth/verify-otp")
def verify_otp(req: OTPVerify):
    if otp_store.get(req.phone) != req.otp:
        raise HTTPException(400, "Invalid OTP")
    token = create_token(req.phone)
    return {"token": token}

# ----- USER SETUP -----
@app.post("/user/setup")
def setup_user(req: SetupRequest, phone: str = Depends(get_current_user)):
    db.collection("users").document(phone).set({
        "name": req.name,
        "contacts": req.contacts,
        "created": firestore.SERVER_TIMESTAMP
    })
    return {"message": "saved"}

# ----- LOCATION -----
@app.post("/user/location")
def update_location(loc: LocationUpdate,
                    phone: str = Depends(get_current_user)):
    db.collection("locations").document(phone).set({
        "lat": loc.lat,
        "lon": loc.lon,
        "time": firestore.SERVER_TIMESTAMP
    })
    return {"message": "updated"}

@app.get("/user/location/{phone}")
def get_location(phone: str):
    doc = db.collection("locations").document(phone).get()
    return doc.to_dict()

# ----- SOS -----
@app.post("/alert/sos")
def sos(req: SOSRequest, phone: str = Depends(get_current_user)):
    db.collection("alerts").add({
        "phone": phone,
        "reason": req.reason,
        "score": req.score,
        "time": firestore.SERVER_TIMESTAMP
    })
    return {"status": "logged"}

# ----- PHOTO UPLOAD -----
@app.post("/upload/photo")
async def upload_photo(file: UploadFile = File(...),
                       phone: str = Depends(get_current_user)):
    bucket = storage.bucket()
    name = f"photos/{phone}_{uuid.uuid4()}.jpg"
    blob = bucket.blob(name)
    blob.upload_from_file(file.file)
    blob.make_public()

    db.collection("alerts").add({
        "phone": phone,
        "photo_url": blob.public_url,
        "time": firestore.SERVER_TIMESTAMP
    })

    return {"url": blob.public_url}

# ----- AUDIO UPLOAD -----
@app.post("/upload/audio")
async def upload_audio(file: UploadFile = File(...),
                       phone: str = Depends(get_current_user)):
    bucket = storage.bucket()
    name = f"audio/{phone}_{uuid.uuid4()}.webm"
    blob = bucket.blob(name)
    blob.upload_from_file(file.file)
    blob.make_public()

    db.collection("alerts").add({
        "phone": phone,
        "audio_url": blob.public_url,
        "time": firestore.SERVER_TIMESTAMP
    })

    return {"url": blob.public_url}
