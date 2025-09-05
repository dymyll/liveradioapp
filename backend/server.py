from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Form, WebSocket, WebSocketDisconnect, Depends, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import os
import uuid
import json
import aiofiles
import asyncio
import logging
import jwt
import hashlib
import re
from passlib.context import CryptContext

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
ROOT_DIR = Path(__file__).parent
from dotenv import load_dotenv
load_dotenv(ROOT_DIR / '.env')

# Security
SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create directories for file uploads
UPLOAD_DIR = ROOT_DIR / "uploads"
AUDIO_DIR = UPLOAD_DIR / "audio"
ARTWORK_DIR = UPLOAD_DIR / "artwork"
STATION_ARTWORK_DIR = UPLOAD_DIR / "stations"

for directory in [UPLOAD_DIR, AUDIO_DIR, ARTWORK_DIR, STATION_ARTWORK_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Create the main app
app = FastAPI(title="Multi-Station Radio Platform API", version="2.0.0")

# Create API router
api_router = APIRouter(prefix="/api")

# WebSocket connection manager for multi-station support
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.station_connections: Dict[str, List[WebSocket]] = {}  # station_id -> connections
        self.dj_connections: Dict[str, WebSocket] = {}  # user_id -> websocket

    async def connect(self, websocket: WebSocket, station_id: str = "platform", user_id: str = None, role: str = "listener"):
        await websocket.accept()
        self.active_connections.append(websocket)
        
        if station_id not in self.station_connections:
            self.station_connections[station_id] = []
        self.station_connections[station_id].append(websocket)
        
        # Track DJ connections separately
        if role in ["dj", "admin"] and user_id:
            self.dj_connections[user_id] = websocket

    def disconnect(self, websocket: WebSocket, user_id: str = None):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        for station_connections in self.station_connections.values():
            if websocket in station_connections:
                station_connections.remove(websocket)
        if user_id and user_id in self.dj_connections:
            del self.dj_connections[user_id]

    async def broadcast_to_station(self, message: str, station_id: str):
        """Broadcast message to all connections in a specific station"""
        if station_id in self.station_connections:
            disconnected = []
            for connection in self.station_connections[station_id]:
                try:
                    await connection.send_text(message)
                except:
                    disconnected.append(connection)
            
            for conn in disconnected:
                self.disconnect(conn)

    async def broadcast_to_platform(self, message: str):
        """Broadcast to platform-wide room"""
        await self.broadcast_to_station(message, "platform")

manager = ConnectionManager()

# Helper functions
def create_station_slug(name: str) -> str:
    """Create URL-friendly slug from station name"""
    slug = re.sub(r'[^a-zA-Z0-9\s-]', '', name.lower())
    slug = re.sub(r'[\s-]+', '-', slug)
    return slug.strip('-')

# Data Models
class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str
    email: str
    password_hash: str
    role: str = "listener"  # listener, artist, dj, admin
    is_active: bool = True
    owned_stations: List[str] = []  # station_ids this user owns
    followed_stations: List[str] = []  # station_ids this user follows
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Station(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    slug: str
    description: Optional[str] = None
    owner_id: str
    owner_name: str
    genre: Optional[str] = None
    artwork_url: Optional[str] = None
    is_active: bool = True
    is_live: bool = False
    current_listeners: int = 0
    total_followers: int = 0
    average_rating: float = 0.0
    total_ratings: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    settings: Dict[str, Any] = {}

class StationRating(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    station_id: str
    rating: int = Field(ge=1, le=5)  # 1-5 star rating
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Song(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    artist_id: str
    artist_name: str
    station_id: str  # Which station this song belongs to
    duration: Optional[int] = None
    file_path: Optional[str] = None
    external_url: Optional[str] = None
    source: str = "upload"
    genre: Optional[str] = None
    artwork_url: Optional[str] = None
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    approved: bool = False

class Playlist(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: Optional[str] = None
    station_id: str  # Which station this playlist belongs to
    created_by: str
    songs: List[str] = []
    is_public: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Schedule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    station_id: str  # Which station this schedule belongs to
    dj_id: str
    dj_name: str
    start_time: datetime
    end_time: datetime
    playlist_id: Optional[str] = None
    is_live: bool = False
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class LiveStream(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    station_id: str  # Which station this stream belongs to
    dj_id: str
    dj_name: str
    title: str
    description: Optional[str] = None
    is_active: bool = True
    current_song: Optional[str] = None
    listener_count: int = 0
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Request/Response Models
class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str
    is_active: bool
    owned_stations: List[str] = []
    followed_stations: List[str] = []
    created_at: datetime

class StationWithDetails(BaseModel):
    id: str
    name: str
    slug: str
    description: Optional[str] = None
    owner_id: str
    owner_name: str
    genre: Optional[str] = None
    artwork_url: Optional[str] = None
    is_active: bool
    is_live: bool
    current_listeners: int
    total_followers: int
    average_rating: float
    total_ratings: int
    created_at: datetime
    user_rating: Optional[int] = None  # Current user's rating if logged in
    featured_artists: List[str] = []  # Top artists on this station

class StationCreate(BaseModel):
    name: str
    description: Optional[str] = None
    genre: Optional[str] = None

class StationUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    genre: Optional[str] = None

class StationRatingCreate(BaseModel):
    rating: int = Field(ge=1, le=5)

class SearchQuery(BaseModel):
    query: str
    search_type: str = "all"  # all, stations, djs, artists

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    role: str = "listener"

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

# Auth functions (unchanged)
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
    
    user = await db.users.find_one({"username": username})
    if user is None:
        raise credentials_exception
    return User(**serialize_doc(user))

async def get_current_user_optional(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Optional authentication - returns None if not authenticated"""
    try:
        return await get_current_user(credentials)
    except:
        return None

async def get_current_dj_or_admin(current_user: User = Depends(get_current_user)):
    if current_user.role not in ["dj", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. DJ or Admin role required."
        )
    return current_user

async def get_station_owner(station_id: str, current_user: User = Depends(get_current_user)):
    """Verify user owns the station or is admin"""
    if current_user.role == "admin":
        return current_user
    
    station = await db.stations.find_one({"id": station_id})
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
    
    if station["owner_id"] != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to manage this station"
        )
    return current_user

def serialize_doc(doc):
    """Convert MongoDB document to JSON serializable format"""
    if doc and "_id" in doc:
        doc.pop("_id")
    return doc

async def calculate_station_rating(station_id: str):
    """Calculate and update station's average rating"""
    pipeline = [
        {"$match": {"station_id": station_id}},
        {"$group": {
            "_id": None,
            "average_rating": {"$avg": "$rating"},
            "total_ratings": {"$sum": 1}
        }}
    ]
    
    result = await db.station_ratings.aggregate(pipeline).to_list(1)
    
    if result:
        avg_rating = round(result[0]["average_rating"], 1)
        total_ratings = result[0]["total_ratings"]
    else:
        avg_rating = 0.0
        total_ratings = 0
    
    # Update station with new ratings
    await db.stations.update_one(
        {"id": station_id},
        {"$set": {
            "average_rating": avg_rating,
            "total_ratings": total_ratings
        }}
    )
    
    return avg_rating, total_ratings

# Authentication endpoints (unchanged)
@api_router.post("/auth/register", response_model=Token)
async def register(user: UserCreate):
    existing_user = await db.users.find_one({"$or": [{"username": user.username}, {"email": user.email}]})
    if existing_user:
        raise HTTPException(status_code=400, detail="Username or email already registered")
    
    hashed_password = get_password_hash(user.password)
    user_doc = User(
        username=user.username,
        email=user.email,
        password_hash=hashed_password,
        role=user.role
    )
    await db.users.insert_one(user_doc.dict())
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    user_response = UserResponse(**user_doc.dict())
    return Token(access_token=access_token, token_type="bearer", user=user_response)

@api_router.post("/auth/login", response_model=Token)
async def login(user_credentials: UserLogin):
    user = await db.users.find_one({"username": user_credentials.username})
    if not user or not verify_password(user_credentials.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    
    user_response = UserResponse(**serialize_doc(user))
    return Token(access_token=access_token, token_type="bearer", user=user_response)

@api_router.get("/auth/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return UserResponse(**current_user.dict())

# Enhanced Search Endpoint
@api_router.post("/search")
async def search_platform(query: str, search_type: str = "all", genre: str = None):
    """Advanced search across stations, DJs, and artists with genre filtering"""
    current_user = None  # Allow unauthenticated search
    
    query = query.lower().strip()
    
    if not query:
        return {"stations": [], "total": 0, "query": query, "search_type": search_type, "genre": genre}
    
    # Build search pipeline
    stations_pipeline = [
        {"$match": {"is_active": True}},
        {"$lookup": {
            "from": "songs",
            "localField": "id",
            "foreignField": "station_id",
            "as": "station_songs"
        }}
    ]
    
    # Build match conditions
    match_conditions = []
    
    # Add search filters based on type
    if search_type == "all":
        search_conditions = [
            {"name": {"$regex": query, "$options": "i"}},
            {"description": {"$regex": query, "$options": "i"}},
            {"owner_name": {"$regex": query, "$options": "i"}},
            {"station_songs.artist_name": {"$regex": query, "$options": "i"}}
        ]
        match_conditions.append({"$or": search_conditions})
    elif search_type == "stations":
        station_conditions = [
            {"name": {"$regex": query, "$options": "i"}},
            {"description": {"$regex": query, "$options": "i"}}
        ]
        match_conditions.append({"$or": station_conditions})
    elif search_type == "djs":
        match_conditions.append({"owner_name": {"$regex": query, "$options": "i"}})
    elif search_type == "artists":
        match_conditions.append({"station_songs.artist_name": {"$regex": query, "$options": "i"}})
    
    # Add genre filter if specified
    if genre and genre.lower() != "all":
        genre_conditions = [
            {"genre": {"$regex": genre, "$options": "i"}},
            {"station_songs.genre": {"$regex": genre, "$options": "i"}}
        ]
        match_conditions.append({"$or": genre_conditions})
    
    # Combine all match conditions
    if match_conditions:
        if len(match_conditions) == 1:
            final_match = match_conditions[0]
        else:
            final_match = {"$and": match_conditions}
        
        stations_pipeline.append({"$match": final_match})
    
    # Add aggregation for featured artists
    stations_pipeline.extend([
        {"$addFields": {
            "featured_artists": {
                "$slice": [
                    {"$setUnion": ["$station_songs.artist_name"]},
                    5
                ]
            }
        }},
        {"$project": {
            "station_songs": 0  # Remove songs from final result
        }},
        {"$sort": {"average_rating": -1, "total_followers": -1}}
    ])
    
    # Execute search
    stations_cursor = db.stations.aggregate(stations_pipeline)
    stations_data = await stations_cursor.to_list(50)  # Limit to 50 results
    
    # Enhance stations with user ratings and live status
    enhanced_stations = []
    for station_data in stations_data:
        station = serialize_doc(station_data)
        
        # Update current listeners
        station["current_listeners"] = len(manager.station_connections.get(station["id"], []))
        
        # Check live status
        live_stream = await db.live_streams.find_one({"station_id": station["id"], "is_active": True})
        station["is_live"] = bool(live_stream)
        
        # Get user's rating if logged in
        if current_user:
            user_rating = await db.station_ratings.find_one({
                "user_id": current_user.id,
                "station_id": station["id"]
            })
            station["user_rating"] = user_rating["rating"] if user_rating else None
        
        enhanced_stations.append(StationWithDetails(**station))
    
    return {
        "stations": enhanced_stations,
        "total": len(enhanced_stations),
        "query": query,
        "search_type": search_type,
        "genre": genre
    }

# Get available genres endpoint
@api_router.get("/genres")
async def get_available_genres():
    """Get all available genres from stations and songs"""
    # Get genres from stations
    station_genres_pipeline = [
        {"$match": {"is_active": True, "genre": {"$ne": None, "$ne": ""}}},
        {"$group": {"_id": "$genre"}},
        {"$sort": {"_id": 1}}
    ]
    
    # Get genres from songs
    song_genres_pipeline = [
        {"$match": {"approved": True, "genre": {"$ne": None, "$ne": ""}}},
        {"$group": {"_id": "$genre"}},
        {"$sort": {"_id": 1}}
    ]
    
    station_genres_cursor = db.stations.aggregate(station_genres_pipeline)
    song_genres_cursor = db.songs.aggregate(song_genres_pipeline)
    
    station_genres = await station_genres_cursor.to_list(100)
    song_genres = await song_genres_cursor.to_list(100)
    
    # Combine and deduplicate genres
    all_genres = set()
    for genre_doc in station_genres:
        if genre_doc["_id"]:
            all_genres.add(genre_doc["_id"])
    
    for genre_doc in song_genres:
        if genre_doc["_id"]:
            all_genres.add(genre_doc["_id"])
    
    return {"genres": sorted(list(all_genres))}

# Station Management
@api_router.post("/stations", response_model=Station)
async def create_station(station_data: StationCreate, current_user: User = Depends(get_current_dj_or_admin)):
    """Create a new radio station"""
    slug = create_station_slug(station_data.name)
    
    # Check if slug already exists
    existing_station = await db.stations.find_one({"slug": slug})
    if existing_station:
        # Add number suffix if slug exists
        counter = 1
        while existing_station:
            new_slug = f"{slug}-{counter}"
            existing_station = await db.stations.find_one({"slug": new_slug})
            counter += 1
        slug = new_slug
    
    station = Station(
        name=station_data.name,
        slug=slug,
        description=station_data.description,
        owner_id=current_user.id,
        owner_name=current_user.username,
        genre=station_data.genre
    )
    
    await db.stations.insert_one(station.dict())
    
    # Add station to user's owned stations
    await db.users.update_one(
        {"id": current_user.id},
        {"$addToSet": {"owned_stations": station.id}}
    )
    
    # Broadcast new station creation
    await manager.broadcast_to_platform(
        json.dumps({
            "type": "station_created",
            "station": station.dict()
        })
    )
    
    return station

@api_router.get("/stations", response_model=List[StationWithDetails])
async def get_all_stations(current_user: Optional[User] = Depends(get_current_user_optional)):
    """Get all active stations for discovery"""
    stations = await db.stations.find({"is_active": True}).to_list(100)
    
    enhanced_stations = []
    for station in stations:
        station_id = station["id"]
        
        # Update current listeners count
        station["current_listeners"] = len(manager.station_connections.get(station_id, []))
        
        # Check if station has active live stream
        live_stream = await db.live_streams.find_one({"station_id": station_id, "is_active": True})
        station["is_live"] = bool(live_stream)
        
        # Get featured artists for this station
        featured_artists_pipeline = [
            {"$match": {"station_id": station_id, "approved": True}},
            {"$group": {"_id": "$artist_name", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 5},
            {"$project": {"_id": 1}}
        ]
        
        featured_artists_cursor = db.songs.aggregate(featured_artists_pipeline)
        featured_artists_data = await featured_artists_cursor.to_list(5)
        station["featured_artists"] = [artist["_id"] for artist in featured_artists_data]
        
        # Get user's rating if logged in
        if current_user:
            user_rating = await db.station_ratings.find_one({
                "user_id": current_user.id,
                "station_id": station_id
            })
            station["user_rating"] = user_rating["rating"] if user_rating else None
        else:
            station["user_rating"] = None
        
        enhanced_stations.append(StationWithDetails(**serialize_doc(station)))
    
    return enhanced_stations

@api_router.get("/stations/{station_slug}", response_model=StationWithDetails)
async def get_station_by_slug(station_slug: str, current_user: Optional[User] = Depends(get_current_user_optional)):
    """Get station details by slug"""
    station = await db.stations.find_one({"slug": station_slug, "is_active": True})
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
    
    # Update live status and listener count
    station_id = station["id"]
    station["current_listeners"] = len(manager.station_connections.get(station_id, []))
    
    live_stream = await db.live_streams.find_one({"station_id": station_id, "is_active": True})
    station["is_live"] = bool(live_stream)
    
    # Get featured artists
    featured_artists_pipeline = [
        {"$match": {"station_id": station_id, "approved": True}},
        {"$group": {"_id": "$artist_name", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5},
        {"$project": {"_id": 1}}
    ]
    
    featured_artists_cursor = db.songs.aggregate(featured_artists_pipeline)
    featured_artists_data = await featured_artists_cursor.to_list(5)
    station["featured_artists"] = [artist["_id"] for artist in featured_artists_data]
    
    # Get user's rating if logged in
    if current_user:
        user_rating = await db.station_ratings.find_one({
            "user_id": current_user.id,
            "station_id": station_id
        })
        station["user_rating"] = user_rating["rating"] if user_rating else None
    else:
        station["user_rating"] = None
    
    return StationWithDetails(**serialize_doc(station))

# Station Rating System
@api_router.post("/stations/{station_id}/rate")
async def rate_station(station_id: str, rating_data: StationRatingCreate, current_user: User = Depends(get_current_user)):
    """Rate a station (1-5 stars)"""
    # Check if station exists
    station = await db.stations.find_one({"id": station_id})
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
    
    # Check if user already rated this station
    existing_rating = await db.station_ratings.find_one({
        "user_id": current_user.id,
        "station_id": station_id
    })
    
    if existing_rating:
        # Update existing rating
        await db.station_ratings.update_one(
            {"user_id": current_user.id, "station_id": station_id},
            {"$set": {
                "rating": rating_data.rating,
                "updated_at": datetime.now(timezone.utc)
            }}
        )
    else:
        # Create new rating
        new_rating = StationRating(
            user_id=current_user.id,
            station_id=station_id,
            rating=rating_data.rating
        )
        await db.station_ratings.insert_one(new_rating.dict())
    
    # Recalculate station's average rating
    await calculate_station_rating(station_id)
    
    return {"message": "Rating saved successfully"}

@api_router.get("/stations/{station_id}/ratings")
async def get_station_ratings(station_id: str):
    """Get station rating statistics"""
    # Check if station exists
    station = await db.stations.find_one({"id": station_id})
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
    
    # Get rating distribution
    pipeline = [
        {"$match": {"station_id": station_id}},
        {"$group": {
            "_id": "$rating",
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": -1}}
    ]
    
    rating_distribution = await db.station_ratings.aggregate(pipeline).to_list(5)
    
    return {
        "average_rating": station["average_rating"],
        "total_ratings": station["total_ratings"],
        "distribution": {str(item["_id"]): item["count"] for item in rating_distribution}
    }

@api_router.put("/stations/{station_id}")
async def update_station(
    station_id: str, 
    station_data: StationUpdate, 
    current_user: User = Depends(get_station_owner)
):
    """Update station details (owner only)"""
    update_data = {k: v for k, v in station_data.dict().items() if v is not None}
    
    if "name" in update_data:
        update_data["slug"] = create_station_slug(update_data["name"])
    
    result = await db.stations.update_one(
        {"id": station_id},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Station not found")
    
    return {"message": "Station updated successfully"}

@api_router.post("/stations/{station_id}/follow")
async def follow_station(station_id: str, current_user: User = Depends(get_current_user)):
    """Follow a station"""
    station = await db.stations.find_one({"id": station_id})
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
    
    # Add to user's followed stations
    await db.users.update_one(
        {"id": current_user.id},
        {"$addToSet": {"followed_stations": station_id}}
    )
    
    # Increment station followers count
    await db.stations.update_one(
        {"id": station_id},
        {"$inc": {"total_followers": 1}}
    )
    
    return {"message": "Station followed successfully"}

@api_router.delete("/stations/{station_id}/follow")
async def unfollow_station(station_id: str, current_user: User = Depends(get_current_user)):
    """Unfollow a station"""
    await db.users.update_one(
        {"id": current_user.id},
        {"$pull": {"followed_stations": station_id}}
    )
    
    await db.stations.update_one(
        {"id": station_id},
        {"$inc": {"total_followers": -1}}
    )
    
    return {"message": "Station unfollowed successfully"}

# Station-specific content endpoints
@api_router.get("/stations/{station_slug}/songs")
async def get_station_songs(station_slug: str, approved_only: bool = True):
    """Get songs for a specific station"""
    station = await db.stations.find_one({"slug": station_slug})
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
    
    query = {"station_id": station["id"]}
    if approved_only:
        query["approved"] = True
    
    songs = await db.songs.find(query).to_list(200)
    return [Song(**serialize_doc(song)) for song in songs]

@api_router.post("/stations/{station_slug}/songs/upload")
async def upload_song_to_station(
    station_slug: str,
    title: str = Form(...),
    artist_name: str = Form(...),
    genre: str = Form(None),
    audio_file: UploadFile = File(...),
    artwork_file: UploadFile = File(None),
    current_user: User = Depends(get_current_user)
):
    """Upload song to a specific station"""
    station = await db.stations.find_one({"slug": station_slug})
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
    
    # Generate unique filename
    audio_filename = f"{uuid.uuid4()}_{audio_file.filename}"
    audio_path = AUDIO_DIR / audio_filename
    
    # Save audio file
    async with aiofiles.open(audio_path, 'wb') as f:
        content = await audio_file.read()
        await f.write(content)
    
    # Save artwork if provided
    artwork_url = None
    if artwork_file:
        artwork_filename = f"{uuid.uuid4()}_{artwork_file.filename}"
        artwork_path = ARTWORK_DIR / artwork_filename
        async with aiofiles.open(artwork_path, 'wb') as f:
            artwork_content = await artwork_file.read()
            await f.write(artwork_content)
        artwork_url = f"/uploads/artwork/{artwork_filename}"
    
    # Create song document
    song = Song(
        title=title,
        artist_id=current_user.id,
        artist_name=artist_name,
        station_id=station["id"],
        file_path=f"/uploads/audio/{audio_filename}",
        genre=genre,
        artwork_url=artwork_url,
        source="upload"
    )
    
    await db.songs.insert_one(song.dict())
    
    # Broadcast to station
    await manager.broadcast_to_station(
        json.dumps({
            "type": "song_upload",
            "station_id": station["id"],
            "song": song.dict()
        }),
        station["id"]
    )
    
    return {"message": "Song uploaded successfully", "id": song.id}

# Station Live Streaming
@api_router.post("/stations/{station_slug}/live/start")
async def start_station_live_stream(
    station_slug: str,
    stream_data: dict,
    current_user: User = Depends(get_current_user)
):
    """Start live stream for a station"""
    station = await db.stations.find_one({"slug": station_slug})
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
    
    # Check if user can broadcast on this station
    if current_user.id != station["owner_id"] and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to broadcast on this station")
    
    # End any existing live streams for this station
    await db.live_streams.update_many(
        {"station_id": station["id"]},
        {"$set": {"is_active": False}}
    )
    
    # Create new live stream
    live_stream = LiveStream(
        station_id=station["id"],
        dj_id=current_user.id,
        dj_name=current_user.username,
        title=stream_data.get("title", "Live Stream"),
        description=stream_data.get("description")
    )
    
    await db.live_streams.insert_one(live_stream.dict())
    
    # Update station live status
    await db.stations.update_one(
        {"id": station["id"]},
        {"$set": {"is_live": True}}
    )
    
    # Broadcast to station listeners
    await manager.broadcast_to_station(
        json.dumps({
            "type": "live_stream_started",
            "station_id": station["id"],
            "station_name": station["name"],
            "dj_name": current_user.username,
            "stream_title": stream_data.get("title", "Live Stream"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }),
        station["id"]
    )
    
    return live_stream

@api_router.post("/stations/{station_slug}/live/stop")
async def stop_station_live_stream(
    station_slug: str,
    current_user: User = Depends(get_current_user)
):
    """Stop live stream for a station"""
    station = await db.stations.find_one({"slug": station_slug})
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
    
    # End live streams
    await db.live_streams.update_many(
        {"station_id": station["id"], "dj_id": current_user.id},
        {"$set": {"is_active": False}}
    )
    
    await db.stations.update_one(
        {"id": station["id"]},
        {"$set": {"is_live": False}}
    )
    
    # Broadcast to station
    await manager.broadcast_to_station(
        json.dumps({
            "type": "live_stream_stopped",
            "station_id": station["id"],
            "dj_name": current_user.username,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }),
        station["id"]
    )
    
    return {"message": "Live stream stopped"}

# WebSocket endpoint with station support
@api_router.websocket("/ws/{station_slug}")
async def websocket_endpoint(websocket: WebSocket, station_slug: str, token: str = None):
    user_id = None
    role = "listener"
    
    # Authenticate WebSocket connection if token provided
    if token:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username = payload.get("sub")
            if username:
                user = await db.users.find_one({"username": username})
                if user:
                    user_id = user["id"]
                    role = user["role"]
        except:
            pass
    
    # Get station
    if station_slug == "platform":
        station_id = "platform"
    else:
        station = await db.stations.find_one({"slug": station_slug})
        station_id = station["id"] if station else "platform"
    
    await manager.connect(websocket, station_id, user_id, role)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle different message types
            if message.get("type") == "chat_message":
                await manager.broadcast_to_station(
                    json.dumps({
                        "type": "chat_message",
                        "station_id": station_id,
                        "message": message.get("message", ""),
                        "username": message.get("username", "Anonymous"),
                        "role": role,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }),
                    station_id
                )
            elif message.get("type") == "dj_control" and role in ["dj", "admin"]:
                # Only DJs/Admins can send control messages
                await manager.broadcast_to_station(
                    json.dumps({
                        "type": "dj_control",
                        "station_id": station_id,
                        "action": message.get("action"),
                        "data": message.get("data", {}),
                        "dj_name": message.get("username", "DJ"),
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }),
                    station_id
                )
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)

# Include router
app.include_router(api_router)

# Serve static files
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)