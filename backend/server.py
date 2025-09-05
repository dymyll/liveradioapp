from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Form, WebSocket, WebSocketDisconnect, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import os
import uuid
import json
import aiofiles
import asyncio
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
ROOT_DIR = Path(__file__).parent
from dotenv import load_dotenv
load_dotenv(ROOT_DIR / '.env')

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

    async def connect(self, websocket: WebSocket, room: str = "general"):
        await websocket.accept()
        self.active_connections.append(websocket)
        if room not in self.connections_by_room:
            self.connections_by_room[room] = []
        self.connections_by_room[room].append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        for room_connections in self.connections_by_room.values():
            if websocket in room_connections:
                room_connections.remove(websocket)

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

manager = ConnectionManager()

# Data Models
class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str
    email: str
    role: str = "listener"  # listener, artist, dj, admin
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

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

# Request Models
class UserCreate(BaseModel):
    username: str
    email: str
    role: str = "listener"

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

# Helper functions
def serialize_doc(doc):
    """Convert MongoDB document to JSON serializable format"""
    if doc and "_id" in doc:
        doc.pop("_id")
    return doc

def serialize_for_json(obj):
    """Convert objects to JSON serializable format"""
    if isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_for_json(item) for item in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat()
    else:
        return obj

# API Routes

# User Management
@api_router.post("/users", response_model=User)
async def create_user(user: UserCreate):
    user_doc = User(**user.dict())
    await db.users.insert_one(user_doc.dict())
    return user_doc

@api_router.get("/users", response_model=List[User])
async def get_users():
    users = await db.users.find().to_list(100)
    return [User(**serialize_doc(user)) for user in users]

# Artist Management
@api_router.post("/artists/submit")
async def submit_artist(artist: ArtistSubmission):
    artist_doc = Artist(**artist.dict())
    await db.artists.insert_one(artist_doc.dict())
    
    # Broadcast new artist submission
    await manager.broadcast_to_room(
        json.dumps({
            "type": "artist_submission",
            "artist": serialize_for_json(artist_doc.dict())
        }),
        "admin"
    )
    
    return {"message": "Artist submission received", "id": artist_doc.id}

@api_router.get("/artists", response_model=List[Artist])
async def get_artists(approved_only: bool = False):
    query = {"approved": True} if approved_only else {}
    artists = await db.artists.find(query).to_list(100)
    return [Artist(**serialize_doc(artist)) for artist in artists]

@api_router.put("/artists/{artist_id}/approve")
async def approve_artist(artist_id: str):
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
    
    # Broadcast new song upload
    await manager.broadcast_to_room(
        json.dumps({
            "type": "song_upload",
            "song": serialize_for_json(song.dict())
        }),
        "admin"
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
async def approve_song(song_id: str):
    result = await db.songs.update_one(
        {"id": song_id},
        {"$set": {"approved": True}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Song not found")
    return {"message": "Song approved"}

# Playlist Management
@api_router.post("/playlists", response_model=Playlist)
async def create_playlist(playlist: PlaylistCreate, created_by: str = "admin"):
    playlist_doc = Playlist(**playlist.dict(), created_by=created_by)
    await db.playlists.insert_one(playlist_doc.dict())
    return playlist_doc

@api_router.get("/playlists", response_model=List[Playlist])
async def get_playlists():
    playlists = await db.playlists.find().to_list(100)
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
async def add_song_to_playlist(playlist_id: str, song_id: str):
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
    
    # Broadcast playlist update
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

# Schedule Management
@api_router.post("/schedule", response_model=Schedule)
async def create_schedule(schedule: ScheduleCreate):
    schedule_doc = Schedule(**schedule.dict())
    await db.schedule.insert_one(schedule_doc.dict())
    
    # Broadcast schedule update
    await manager.broadcast_to_room(
        json.dumps({
            "type": "schedule_update",
            "schedule": serialize_for_json(schedule_doc.dict())
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

# Live streaming status
@api_router.post("/live/{dj_id}/start")
async def start_live_stream(dj_id: str):
    # Update schedule to mark as live
    await db.schedule.update_many(
        {"dj_id": dj_id, "is_live": True},
        {"$set": {"is_live": False}}
    )
    
    now = datetime.now(timezone.utc)
    await db.schedule.update_one(
        {
            "dj_id": dj_id,
            "start_time": {"$lte": now},
            "end_time": {"$gte": now}
        },
        {"$set": {"is_live": True}}
    )
    
    # Broadcast live status
    await manager.broadcast_to_room(
        json.dumps({
            "type": "live_stream_started",
            "dj_id": dj_id,
            "timestamp": now.isoformat()
        }),
        "general"
    )
    
    return {"message": "Live stream started"}

@api_router.post("/live/{dj_id}/stop")
async def stop_live_stream(dj_id: str):
    await db.schedule.update_many(
        {"dj_id": dj_id},
        {"$set": {"is_live": False}}
    )
    
    # Broadcast live status
    await manager.broadcast_to_room(
        json.dumps({
            "type": "live_stream_stopped",
            "dj_id": dj_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }),
        "general"
    )
    
    return {"message": "Live stream stopped"}

# WebSocket endpoint
@api_router.websocket("/ws/{room}")
async def websocket_endpoint(websocket: WebSocket, room: str):
    await manager.connect(websocket, room)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Echo message to all clients in room
            await manager.broadcast_to_room(
                json.dumps({
                    "type": "chat_message",
                    "room": room,
                    "message": message.get("message", ""),
                    "username": message.get("username", "Anonymous"),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }),
                room
            )
    except WebSocketDisconnect:
        manager.disconnect(websocket)

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