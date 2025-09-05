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

for directory in [UPLOAD_DIR, AUDIO_DIR, ARTWORK_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Create the main app
app = FastAPI(title="Radio Station API", version="1.0.0")

# Create API router
api_router = APIRouter(prefix="/api")

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.connections_by_room: Dict[str, List[WebSocket]] = {}
        self.dj_connections: Dict[str, WebSocket] = {}  # Track DJ connections

    async def connect(self, websocket: WebSocket, room: str = "general", user_id: str = None, role: str = "listener"):
        await websocket.accept()
        self.active_connections.append(websocket)
        if room not in self.connections_by_room:
            self.connections_by_room[room] = []
        self.connections_by_room[room].append(websocket)
        
        # Track DJ connections separately
        if role in ["dj", "admin"] and user_id:
            self.dj_connections[user_id] = websocket

    def disconnect(self, websocket: WebSocket, user_id: str = None):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        for room_connections in self.connections_by_room.values():
            if websocket in room_connections:
                room_connections.remove(websocket)
        if user_id and user_id in self.dj_connections:
            del self.dj_connections[user_id]

    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except:
            self.disconnect(websocket)

    async def broadcast_to_room(self, message: str, room: str):
        if room in self.connections_by_room:
            disconnected = []
            for connection in self.connections_by_room[room]:
                try:
                    await connection.send_text(message)
                except:
                    disconnected.append(connection)
            
            for conn in disconnected:
                self.disconnect(conn)

    async def broadcast_to_djs(self, message: str):
        """Broadcast message only to connected DJs"""
        disconnected = []
        for user_id, websocket in self.dj_connections.items():
            try:
                await websocket.send_text(message)
            except:
                disconnected.append(user_id)
        
        for user_id in disconnected:
            if user_id in self.dj_connections:
                del self.dj_connections[user_id]

manager = ConnectionManager()

# Data Models
class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str
    email: str
    password_hash: str
    role: str = "listener"  # listener, artist, dj, admin
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime

class Artist(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    bio: Optional[str] = None
    email: str
    social_links: Optional[Dict[str, str]] = {}
    approved: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Song(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    artist_id: str
    artist_name: str
    duration: Optional[int] = None  # in seconds
    file_path: Optional[str] = None
    external_url: Optional[str] = None
    source: str = "upload"  # upload, spotify, soundcloud
    genre: Optional[str] = None
    artwork_url: Optional[str] = None
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    approved: bool = False

class Playlist(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: Optional[str] = None
    created_by: str  # user_id
    songs: List[str] = []  # song_ids
    is_public: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Schedule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
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
    dj_id: str
    dj_name: str
    title: str
    description: Optional[str] = None
    is_active: bool = True
    current_song: Optional[str] = None
    listener_count: int = 0
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Request/Response Models
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

class ArtistSubmission(BaseModel):
    name: str
    bio: Optional[str] = None
    email: str
    social_links: Optional[Dict[str, str]] = {}

class PlaylistCreate(BaseModel):
    name: str
    description: Optional[str] = None
    is_public: bool = True

class ScheduleCreate(BaseModel):
    title: str
    dj_id: str
    dj_name: str
    start_time: datetime
    end_time: datetime
    playlist_id: Optional[str] = None
    description: Optional[str] = None

class LiveStreamCreate(BaseModel):
    title: str
    description: Optional[str] = None

class DJControl(BaseModel):
    action: str  # play, pause, next, previous, volume, seek
    data: Optional[Dict[str, Any]] = {}

# Auth functions
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

async def get_current_dj_or_admin(current_user: User = Depends(get_current_user)):
    if current_user.role not in ["dj", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. DJ or Admin role required."
        )
    return current_user

# Helper functions
def serialize_doc(doc):
    """Convert MongoDB document to JSON serializable format"""
    if doc and "_id" in doc:
        doc.pop("_id")
    return doc

# Authentication endpoints
@api_router.post("/auth/register", response_model=Token)
async def register(user: UserCreate):
    # Check if user exists
    existing_user = await db.users.find_one({"$or": [{"username": user.username}, {"email": user.email}]})
    if existing_user:
        raise HTTPException(status_code=400, detail="Username or email already registered")
    
    # Create user
    hashed_password = get_password_hash(user.password)
    user_doc = User(
        username=user.username,
        email=user.email,
        password_hash=hashed_password,
        role=user.role
    )
    await db.users.insert_one(user_doc.dict())
    
    # Create token
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

# User Management
@api_router.post("/users", response_model=User)
async def create_user(user: UserCreate, current_user: User = Depends(get_current_dj_or_admin)):
    hashed_password = get_password_hash(user.password)
    user_doc = User(
        username=user.username,
        email=user.email,
        password_hash=hashed_password,
        role=user.role
    )
    await db.users.insert_one(user_doc.dict())
    return user_doc

@api_router.get("/users", response_model=List[UserResponse])
async def get_users(current_user: User = Depends(get_current_dj_or_admin)):
    users = await db.users.find().to_list(100)
    return [UserResponse(**serialize_doc(user)) for user in users]

# Artist Management
@api_router.post("/artists/submit")
async def submit_artist(artist: ArtistSubmission):
    artist_doc = Artist(**artist.dict())
    await db.artists.insert_one(artist_doc.dict())
    
    # Broadcast to DJs/Admins only
    await manager.broadcast_to_djs(
        json.dumps({
            "type": "artist_submission",
            "artist": artist_doc.dict()
        })
    )
    
    return {"message": "Artist submission received", "id": artist_doc.id}

@api_router.get("/artists", response_model=List[Artist])
async def get_artists(approved_only: bool = False):
    query = {"approved": True} if approved_only else {}
    artists = await db.artists.find(query).to_list(100)
    return [Artist(**serialize_doc(artist)) for artist in artists]

@api_router.put("/artists/{artist_id}/approve")
async def approve_artist(artist_id: str, current_user: User = Depends(get_current_dj_or_admin)):
    result = await db.artists.update_one(
        {"id": artist_id},
        {"$set": {"approved": True}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Artist not found")
    return {"message": "Artist approved"}

# Song Management
@api_router.post("/songs/upload")
async def upload_song(
    title: str = Form(...),
    artist_name: str = Form(...),
    genre: str = Form(None),
    audio_file: UploadFile = File(...),
    artwork_file: UploadFile = File(None)
):
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
        artist_id="pending",
        artist_name=artist_name,
        file_path=f"/uploads/audio/{audio_filename}",
        genre=genre,
        artwork_url=artwork_url,
        source="upload"
    )
    
    await db.songs.insert_one(song.dict())
    
    # Broadcast to DJs/Admins only
    await manager.broadcast_to_djs(
        json.dumps({
            "type": "song_upload",
            "song": song.dict()
        })
    )
    
    return {"message": "Song uploaded successfully", "id": song.id}

@api_router.get("/songs", response_model=List[Song])
async def get_songs(approved_only: bool = False, genre: str = None):
    query = {}
    if approved_only:
        query["approved"] = True
    if genre:
        query["genre"] = genre
    
    songs = await db.songs.find(query).to_list(200)
    return [Song(**serialize_doc(song)) for song in songs]

@api_router.get("/songs/{song_id}")
async def get_song(song_id: str):
    song = await db.songs.find_one({"id": song_id})
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    return Song(**serialize_doc(song))

@api_router.put("/songs/{song_id}/approve")
async def approve_song(song_id: str, current_user: User = Depends(get_current_dj_or_admin)):
    result = await db.songs.update_one(
        {"id": song_id},
        {"$set": {"approved": True}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Song not found")
    return {"message": "Song approved"}

# Playlist Management
@api_router.post("/playlists", response_model=Playlist)
async def create_playlist(playlist: PlaylistCreate, current_user: User = Depends(get_current_user)):
    playlist_doc = Playlist(**playlist.dict(), created_by=current_user.id)
    await db.playlists.insert_one(playlist_doc.dict())
    return playlist_doc

@api_router.get("/playlists", response_model=List[Playlist])
async def get_playlists():
    playlists = await db.playlists.find({"is_public": True}).to_list(100)
    return [Playlist(**serialize_doc(playlist)) for playlist in playlists]

@api_router.get("/playlists/{playlist_id}")
async def get_playlist_with_songs(playlist_id: str):
    playlist = await db.playlists.find_one({"id": playlist_id})
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    playlist = serialize_doc(playlist)
    
    # Get full song details
    if playlist.get('songs'):
        songs_data = await db.songs.find({"id": {"$in": playlist['songs']}}).to_list(100)
        playlist['songs_details'] = [Song(**serialize_doc(song)) for song in songs_data]
    
    return playlist

@api_router.post("/playlists/{playlist_id}/songs/{song_id}")
async def add_song_to_playlist(playlist_id: str, song_id: str, current_user: User = Depends(get_current_dj_or_admin)):
    # Check if song exists
    song = await db.songs.find_one({"id": song_id})
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    
    # Update playlist
    result = await db.playlists.update_one(
        {"id": playlist_id},
        {
            "$addToSet": {"songs": song_id},
            "$set": {"updated_at": datetime.now(timezone.utc)}
        }
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    # Broadcast playlist update to all users
    await manager.broadcast_to_room(
        json.dumps({
            "type": "playlist_update",
            "playlist_id": playlist_id,
            "action": "song_added",
            "song_id": song_id
        }),
        "general"
    )
    
    return {"message": "Song added to playlist"}

# Schedule Management (DJ/Admin only)
@api_router.post("/schedule", response_model=Schedule)
async def create_schedule(schedule: ScheduleCreate, current_user: User = Depends(get_current_dj_or_admin)):
    schedule_doc = Schedule(**schedule.dict())
    await db.schedule.insert_one(schedule_doc.dict())
    
    # Broadcast schedule update to all users
    await manager.broadcast_to_room(
        json.dumps({
            "type": "schedule_update",
            "schedule": schedule_doc.dict()
        }),
        "general"
    )
    
    return schedule_doc

@api_router.get("/schedule", response_model=List[Schedule])
async def get_schedule():
    schedules = await db.schedule.find().sort("start_time", 1).to_list(100)
    return [Schedule(**serialize_doc(schedule)) for schedule in schedules]

@api_router.get("/schedule/now")
async def get_current_show():
    now = datetime.now(timezone.utc)
    current_show = await db.schedule.find_one({
        "start_time": {"$lte": now},
        "end_time": {"$gte": now}
    })
    
    if current_show:
        return Schedule(**serialize_doc(current_show))
    return {"message": "No live show currently"}

# Live Streaming (DJ/Admin only)
@api_router.post("/live/start", response_model=LiveStream)
async def start_live_stream(stream_data: LiveStreamCreate, current_user: User = Depends(get_current_dj_or_admin)):
    # End any existing live streams by this DJ
    await db.live_streams.update_many(
        {"dj_id": current_user.id},
        {"$set": {"is_active": False}}
    )
    
    # Create new live stream
    live_stream = LiveStream(
        dj_id=current_user.id,
        dj_name=current_user.username,
        title=stream_data.title,
        description=stream_data.description
    )
    
    await db.live_streams.insert_one(live_stream.dict())
    
    # Update schedule to mark as live
    now = datetime.now(timezone.utc)
    await db.schedule.update_one(
        {
            "dj_id": current_user.id,
            "start_time": {"$lte": now},
            "end_time": {"$gte": now}
        },
        {"$set": {"is_live": True}}
    )
    
    # Broadcast live status to all users
    await manager.broadcast_to_room(
        json.dumps({
            "type": "live_stream_started",
            "dj_id": current_user.id,
            "dj_name": current_user.username,
            "stream_title": stream_data.title,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }),
        "general"
    )
    
    return live_stream

@api_router.post("/live/stop")
async def stop_live_stream(current_user: User = Depends(get_current_dj_or_admin)):
    # End live streams
    await db.live_streams.update_many(
        {"dj_id": current_user.id},
        {"$set": {"is_active": False}}
    )
    
    await db.schedule.update_many(
        {"dj_id": current_user.id},
        {"$set": {"is_live": False}}
    )
    
    # Broadcast live status to all users
    await manager.broadcast_to_room(
        json.dumps({
            "type": "live_stream_stopped",
            "dj_id": current_user.id,
            "dj_name": current_user.username,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }),
        "general"
    )
    
    return {"message": "Live stream stopped"}

@api_router.get("/live/status")
async def get_live_status():
    live_stream = await db.live_streams.find_one({"is_active": True})
    if live_stream:
        return LiveStream(**serialize_doc(live_stream))
    return {"message": "No active live stream"}

# DJ Controls (DJ/Admin only)
@api_router.post("/dj/control")
async def dj_control(control: DJControl, current_user: User = Depends(get_current_dj_or_admin)):
    # Broadcast DJ control to all listeners
    await manager.broadcast_to_room(
        json.dumps({
            "type": "dj_control",
            "dj_id": current_user.id,
            "dj_name": current_user.username,
            "action": control.action,
            "data": control.data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }),
        "general"
    )
    
    return {"message": f"DJ control '{control.action}' broadcasted"}

# WebSocket endpoint
@api_router.websocket("/ws/{room}")
async def websocket_endpoint(websocket: WebSocket, room: str, token: str = None):
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
    
    await manager.connect(websocket, room, user_id, role)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle different message types
            if message.get("type") == "chat_message":
                # Echo message to all clients in room
                await manager.broadcast_to_room(
                    json.dumps({
                        "type": "chat_message",
                        "room": room,
                        "message": message.get("message", ""),
                        "username": message.get("username", "Anonymous"),
                        "role": role,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }),
                    room
                )
            elif message.get("type") == "dj_control" and role in ["dj", "admin"]:
                # Only DJs/Admins can send control messages
                await manager.broadcast_to_room(
                    json.dumps({
                        "type": "dj_control",
                        "action": message.get("action"),
                        "data": message.get("data", {}),
                        "dj_name": message.get("username", "DJ"),
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }),
                    "general"
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