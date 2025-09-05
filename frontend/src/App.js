import React, { useState, useEffect, createContext, useContext, useReducer } from 'react';
import { BrowserRouter, Routes, Route, useParams, useNavigate, Link } from 'react-router-dom';
import axios from 'axios';
import './App.css';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
const WS_URL = BACKEND_URL.replace('https:', 'wss:').replace('http:', 'ws:');

// Context for application state
const RadioContext = createContext();

// State management
const initialState = {
  currentSong: null,
  isPlaying: false,
  currentUser: null,
  isAuthenticated: false,
  token: localStorage.getItem('token'),
  
  // Platform-wide data
  allStations: [],
  
  // Current station data
  currentStation: null,
  stationSongs: [],
  stationPlaylists: [],
  stationSchedule: [],
  liveStream: null,
  isLive: false,
  
  notifications: []
};

function radioReducer(state, action) {
  switch (action.type) {
    case 'SET_ALL_STATIONS':
      return { ...state, allStations: action.payload };
    case 'SET_CURRENT_STATION':
      return { ...state, currentStation: action.payload };
    case 'SET_STATION_SONGS':
      return { ...state, stationSongs: action.payload };
    case 'SET_STATION_PLAYLISTS':
      return { ...state, stationPlaylists: action.payload };
    case 'SET_STATION_SCHEDULE':
      return { ...state, stationSchedule: action.payload };
    case 'SET_LIVE_STREAM':
      return { ...state, liveStream: action.payload };
    case 'SET_CURRENT_SONG':
      return { ...state, currentSong: action.payload };
    case 'TOGGLE_PLAY':
      return { ...state, isPlaying: !state.isPlaying };
    case 'SET_USER':
      return { 
        ...state, 
        currentUser: action.payload, 
        isAuthenticated: !!action.payload 
      };
    case 'SET_TOKEN':
      return { ...state, token: action.payload };
    case 'LOGOUT':
      localStorage.removeItem('token');
      return { 
        ...state, 
        currentUser: null, 
        isAuthenticated: false, 
        token: null 
      };
    case 'SET_LIVE_STATUS':
      return { ...state, isLive: action.payload };
    case 'ADD_NOTIFICATION':
      return { 
        ...state, 
        notifications: [...state.notifications, { 
          id: Date.now(), 
          ...action.payload 
        }] 
      };
    case 'REMOVE_NOTIFICATION':
      return { 
        ...state, 
        notifications: state.notifications.filter(n => n.id !== action.payload) 
      };
    default:
      return state;
  }
}

// Provider component
function RadioProvider({ children }) {
  const [state, dispatch] = useReducer(radioReducer, initialState);
  const [socket, setSocket] = useState(null);

  // Set up axios interceptor for auth
  useEffect(() => {
    if (state.token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${state.token}`;
    } else {
      delete axios.defaults.headers.common['Authorization'];
    }
  }, [state.token]);

  // Load user data if token exists
  useEffect(() => {
    if (state.token && !state.currentUser) {
      loadCurrentUser();
    }
  }, [state.token]);

  const loadCurrentUser = async () => {
    try {
      const response = await axios.get(`${API}/auth/me`);
      dispatch({ type: 'SET_USER', payload: response.data });
    } catch (error) {
      console.error('Error loading user:', error);
      dispatch({ type: 'LOGOUT' });
    }
  };

  const login = async (username, password) => {
    try {
      const response = await axios.post(`${API}/auth/login`, {
        username,
        password
      });
      
      const { access_token, user } = response.data;
      localStorage.setItem('token', access_token);
      dispatch({ type: 'SET_TOKEN', payload: access_token });
      dispatch({ type: 'SET_USER', payload: user });
      
      return { success: true };
    } catch (error) {
      return { 
        success: false, 
        message: error.response?.data?.detail || 'Login failed' 
      };
    }
  };

  const register = async (username, email, password, role = 'listener') => {
    try {
      const response = await axios.post(`${API}/auth/register`, {
        username,
        email,
        password,
        role
      });
      
      const { access_token, user } = response.data;
      localStorage.setItem('token', access_token);
      dispatch({ type: 'SET_TOKEN', payload: access_token });
      dispatch({ type: 'SET_USER', payload: user });
      
      return { success: true };
    } catch (error) {
      return { 
        success: false, 
        message: error.response?.data?.detail || 'Registration failed' 
      };
    }
  };

  const logout = () => {
    dispatch({ type: 'LOGOUT' });
  };

  const loadAllStations = async () => {
    try {
      const response = await axios.get(`${API}/stations`);
      dispatch({ type: 'SET_ALL_STATIONS', payload: response.data });
    } catch (error) {
      console.error('Error loading stations:', error);
    }
  };

  const loadStationData = async (stationSlug) => {
    try {
      const [stationResponse, songsResponse] = await Promise.all([
        axios.get(`${API}/stations/${stationSlug}`),
        axios.get(`${API}/stations/${stationSlug}/songs`)
      ]);
      
      dispatch({ type: 'SET_CURRENT_STATION', payload: stationResponse.data });
      dispatch({ type: 'SET_STATION_SONGS', payload: songsResponse.data });
      dispatch({ type: 'SET_LIVE_STATUS', payload: stationResponse.data.is_live });
      
    } catch (error) {
      console.error('Error loading station data:', error);
    }
  };

  const createStation = async (name, description, genre) => {
    try {
      const response = await axios.post(`${API}/stations`, {
        name,
        description,
        genre
      });
      return { success: true, station: response.data };
    } catch (error) {
      return { 
        success: false, 
        message: error.response?.data?.detail || 'Failed to create station' 
      };
    }
  };

  const connectToStation = (stationSlug) => {
    if (socket) {
      socket.close();
    }

    const wsUrl = state.token 
      ? `${WS_URL}/api/ws/${stationSlug}?token=${state.token}`
      : `${WS_URL}/api/ws/${stationSlug}`;
    
    const ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
      console.log(`Connected to station: ${stationSlug}`);
      setSocket(ws);
    };
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      switch (data.type) {
        case 'live_stream_started':
          dispatch({ type: 'SET_LIVE_STATUS', payload: true });
          dispatch({ 
            type: 'ADD_NOTIFICATION', 
            payload: { 
              message: `🎙️ ${data.dj_name} is now live: ${data.stream_title}`, 
              type: 'info' 
            } 
          });
          break;
        case 'live_stream_stopped':
          dispatch({ type: 'SET_LIVE_STATUS', payload: false });
          break;
        case 'dj_control':
          if (data.action === 'play' && data.data.song) {
            dispatch({ type: 'SET_CURRENT_SONG', payload: data.data.song });
            dispatch({ type: 'TOGGLE_PLAY', payload: true });
          }
          break;
        case 'song_upload':
          dispatch({ 
            type: 'ADD_NOTIFICATION', 
            payload: { 
              message: `🎵 New song: ${data.song.title}`, 
              type: 'success' 
            } 
          });
          break;
        default:
          break;
      }
    };
    
    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setSocket(null);
    };
    
    return ws;
  };

  const value = {
    state,
    dispatch,
    socket,
    login,
    register,
    logout,
    loadAllStations,
    loadStationData,
    createStation,
    connectToStation
  };

  return (
    <RadioContext.Provider value={value}>
      {children}
    </RadioContext.Provider>
  );
}

function useRadio() {
  const context = useContext(RadioContext);
  if (!context) {
    throw new Error('useRadio must be used within a RadioProvider');
  }
  return context;
}

// Components

// Authentication Modal (unchanged from previous version)
function AuthModal({ isLogin, onClose, onSwitch }) {
  const { login, register } = useRadio();
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    role: 'listener'
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError('');

    const result = isLogin 
      ? await login(formData.username, formData.password)
      : await register(formData.username, formData.email, formData.password, formData.role);

    if (result.success) {
      onClose();
    } else {
      setError(result.message);
    }
    setIsSubmitting(false);
  };

  const handleInputChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  return (
    <div className="auth-modal-overlay" onClick={onClose}>
      <div className="auth-modal" onClick={e => e.stopPropagation()}>
        <div className="auth-modal-header">
          <h2>{isLogin ? '🎵 Sign In' : '🎤 Join the Platform'}</h2>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>
        
        <form onSubmit={handleSubmit} className="auth-form">
          {error && <div className="error-message">{error}</div>}
          
          <div className="form-group">
            <label>Username</label>
            <input
              type="text"
              name="username"
              value={formData.username}
              onChange={handleInputChange}
              required
              placeholder="Enter your username"
            />
          </div>
          
          {!isLogin && (
            <div className="form-group">
              <label>Email</label>
              <input
                type="email"
                name="email"
                value={formData.email}
                onChange={handleInputChange}
                required
                placeholder="Enter your email"
              />
            </div>
          )}
          
          <div className="form-group">
            <label>Password</label>
            <input
              type="password"
              name="password"
              value={formData.password}
              onChange={handleInputChange}
              required
              placeholder="Enter your password"
            />
          </div>
          
          {!isLogin && (
            <div className="form-group">
              <label>Role</label>
              <select
                name="role"
                value={formData.role}
                onChange={handleInputChange}
              >
                <option value="listener">🎧 Listener</option>
                <option value="artist">🎤 Artist</option>
                <option value="dj">🎙️ DJ</option>
              </select>
            </div>
          )}
          
          <button 
            type="submit" 
            disabled={isSubmitting}
            className="auth-submit-btn"
          >
            {isSubmitting ? '⏳ Processing...' : (isLogin ? '🎵 Sign In' : '🚀 Join Platform')}
          </button>
        </form>
        
        <div className="auth-switch">
          {isLogin ? (
            <p>New to the platform? <button onClick={onSwitch}>Create Account</button></p>
          ) : (
            <p>Already have an account? <button onClick={onSwitch}>Sign In</button></p>
          )}
        </div>
      </div>
    </div>
  );
}

// Platform Header
function PlatformHeader() {
  const { state, logout } = useRadio();
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [isLogin, setIsLogin] = useState(true);
  
  return (
    <header className="platform-header">
      <div className="header-content">
        <div className="logo">
          <Link to="/">
            <h1>📻 Multi-Station Radio Platform</h1>
          </Link>
        </div>
        
        <div className="user-info">
          {state.isAuthenticated ? (
            <div className="user-actions">
              <span>Welcome, {state.currentUser.username}</span>
              <span className={`role-badge ${state.currentUser.role}`}>
                {state.currentUser.role}
              </span>
              {(state.currentUser.role === 'dj' || state.currentUser.role === 'admin') && (
                <Link to="/create-station" className="create-station-btn">
                  Create Station
                </Link>
              )}
              <button onClick={logout} className="logout-btn">Logout</button>
            </div>
          ) : (
            <div className="auth-buttons">
              <button 
                onClick={() => {
                  setIsLogin(true);
                  setShowAuthModal(true);
                }}
                className="auth-btn login-btn"
              >
                Sign In
              </button>
              <button 
                onClick={() => {
                  setIsLogin(false);
                  setShowAuthModal(true);
                }}
                className="auth-btn register-btn"
              >
                Join Platform
              </button>
            </div>
          )}
        </div>
      </div>
      
      {showAuthModal && (
        <AuthModal
          isLogin={isLogin}
          onClose={() => setShowAuthModal(false)}
          onSwitch={() => setIsLogin(!isLogin)}
        />
      )}
    </header>
  );
}

// Station Discovery Page
function StationDiscovery() {
  const { state, loadAllStations } = useRadio();
  const [filter, setFilter] = useState('');
  const [selectedGenre, setSelectedGenre] = useState('');

  useEffect(() => {
    loadAllStations();
  }, []);

  const filteredStations = state.allStations.filter(station => {
    const matchesFilter = station.name.toLowerCase().includes(filter.toLowerCase()) ||
                         station.description?.toLowerCase().includes(filter.toLowerCase()) ||
                         station.owner_name.toLowerCase().includes(filter.toLowerCase());
    const matchesGenre = !selectedGenre || station.genre === selectedGenre;
    return matchesFilter && matchesGenre;
  });

  const genres = [...new Set(state.allStations.map(station => station.genre).filter(Boolean))];

  return (
    <div className="station-discovery">
      <div className="discovery-header">
        <h1>🎵 Discover Radio Stations</h1>
        <p>Find your favorite DJs and discover new music</p>
        
        <div className="discovery-filters">
          <input
            type="text"
            placeholder="Search stations, DJs, or descriptions..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="search-input"
          />
          <select 
            value={selectedGenre} 
            onChange={(e) => setSelectedGenre(e.target.value)}
            className="genre-filter"
          >
            <option value="">All Genres</option>
            {genres.map(genre => (
              <option key={genre} value={genre}>{genre}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="stations-grid">
        {filteredStations.map(station => (
          <div key={station.id} className="station-card">
            <div className="station-header">
              <div className="station-info">
                <h3>
                  <Link to={`/station/${station.slug}`}>
                    📻 {station.name}
                  </Link>
                </h3>
                <p className="station-owner">by {station.owner_name}</p>
                {station.genre && <span className="genre-badge">{station.genre}</span>}
              </div>
              
              {station.is_live && (
                <div className="live-badge">
                  <span className="live-dot"></span>
                  LIVE
                </div>
              )}
            </div>
            
            {station.description && (
              <p className="station-description">{station.description}</p>
            )}
            
            <div className="station-stats">
              <span>👥 {station.current_listeners} listening</span>
              <span>❤️ {station.total_followers} followers</span>
            </div>
            
            <div className="station-actions">
              <Link to={`/station/${station.slug}`} className="listen-btn">
                🎧 Listen Now
              </Link>
            </div>
          </div>
        ))}
      </div>

      {filteredStations.length === 0 && (
        <div className="no-stations">
          <h3>No stations found</h3>
          <p>Try adjusting your search criteria or create your own station!</p>
        </div>
      )}
    </div>
  );
}

// Create Station Page
function CreateStation() {
  const { state, createStation } = useRadio();
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    genre: ''
  });
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsCreating(true);
    setError('');

    const result = await createStation(formData.name, formData.description, formData.genre);
    
    if (result.success) {
      navigate(`/station/${result.station.slug}`);
    } else {
      setError(result.message);
    }
    setIsCreating(false);
  };

  const handleInputChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  if (!state.isAuthenticated || (state.currentUser?.role !== 'dj' && state.currentUser?.role !== 'admin')) {
    return (
      <div className="create-station-unauthorized">
        <h2>🚫 Access Denied</h2>
        <p>You need to be signed in as a DJ or Admin to create a station.</p>
        <Link to="/" className="back-home-btn">← Back to Home</Link>
      </div>
    );
  }

  return (
    <div className="create-station-page">
      <div className="create-station-form">
        <div className="form-header">
          <h2>📻 Create Your Radio Station</h2>
          <p>Launch your own station and start broadcasting to the world!</p>
        </div>
        
        <form onSubmit={handleSubmit}>
          {error && <div className="error-message">{error}</div>}
          
          <div className="form-group">
            <label htmlFor="name">Station Name *</label>
            <input
              type="text"
              id="name"
              name="name"
              value={formData.name}
              onChange={handleInputChange}
              required
              placeholder="e.g. Mike's Indie Rock Station"
            />
            <small>This will be used to create your unique URL</small>
          </div>
          
          <div className="form-group">
            <label htmlFor="description">Description</label>
            <textarea
              id="description"
              name="description"
              value={formData.description}
              onChange={handleInputChange}
              placeholder="Tell listeners what makes your station special..."
              rows="4"
            />
          </div>
          
          <div className="form-group">
            <label htmlFor="genre">Primary Genre</label>
            <select
              id="genre"
              name="genre"
              value={formData.genre}
              onChange={handleInputChange}
            >
              <option value="">Select a genre</option>
              <option value="Indie Rock">Indie Rock</option>
              <option value="Indie Pop">Indie Pop</option>
              <option value="Alternative">Alternative</option>
              <option value="Folk">Folk</option>
              <option value="Electronic">Electronic</option>
              <option value="Hip Hop">Hip Hop</option>
              <option value="R&B">R&B</option>
              <option value="Jazz">Jazz</option>
              <option value="Talk Radio">Talk Radio</option>
              <option value="Mix">Mix</option>
            </select>
          </div>
          
          <button 
            type="submit" 
            disabled={isCreating}
            className="create-btn"
          >
            {isCreating ? '⏳ Creating Station...' : '🚀 Create My Station'}
          </button>
        </form>
      </div>
    </div>
  );
}

// Individual Station Page
function StationPage() {
  const { stationSlug } = useParams();
  const { state, loadStationData, connectToStation } = useRadio();
  const [currentTab, setCurrentTab] = useState('listen');

  useEffect(() => {
    if (stationSlug) {
      loadStationData(stationSlug);
      connectToStation(stationSlug);
    }
  }, [stationSlug]);

  if (!state.currentStation) {
    return (
      <div className="loading-station">
        <div className="spinner"></div>
        <p>Loading station...</p>
      </div>
    );
  }

  const isOwner = state.isAuthenticated && 
    (state.currentUser?.id === state.currentStation.owner_id || state.currentUser?.role === 'admin');

  return (
    <div className="station-page">
      <div className="station-header">
        <div className="station-info">
          <h1>📻 {state.currentStation.name}</h1>
          <p className="station-owner">by {state.currentStation.owner_name}</p>
          {state.currentStation.description && (
            <p className="station-description">{state.currentStation.description}</p>
          )}
          
          <div className="station-meta">
            {state.currentStation.genre && (
              <span className="genre-badge">{state.currentStation.genre}</span>
            )}
            <span className="listeners-count">
              👥 {state.currentStation.current_listeners} listening
            </span>
            <span className="followers-count">
              ❤️ {state.currentStation.total_followers} followers
            </span>
          </div>
        </div>
        
        {state.isLive && (
          <div className="live-indicator-large">
            <span className="live-dot"></span>
            LIVE ON AIR
          </div>
        )}
      </div>

      <nav className="station-nav">
        <button 
          className={currentTab === 'listen' ? 'active' : ''}
          onClick={() => setCurrentTab('listen')}
        >
          🎵 Listen
        </button>
        <button 
          className={currentTab === 'upload' ? 'active' : ''}
          onClick={() => setCurrentTab('upload')}
        >
          📤 Add Music
        </button>
        {isOwner && (
          <button 
            className={currentTab === 'manage' ? 'active' : ''}
            onClick={() => setCurrentTab('manage')}
          >
            🎙️ Manage Station
          </button>
        )}
      </nav>

      <main className="station-content">
        {currentTab === 'listen' && <StationListen />}
        {currentTab === 'upload' && <StationUpload />}
        {currentTab === 'manage' && isOwner && <StationManage />}
      </main>
    </div>
  );
}

// Station Listen Tab
function StationListen() {
  const { state, dispatch } = useRadio();
  const [audio] = useState(new Audio());
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);

  // Audio player logic (similar to previous version but station-specific)
  useEffect(() => {
    const updateTime = () => setCurrentTime(audio.currentTime);
    const updateDuration = () => setDuration(audio.duration);
    
    audio.addEventListener('timeupdate', updateTime);
    audio.addEventListener('loadedmetadata', updateDuration);
    audio.addEventListener('ended', () => {
      dispatch({ type: 'TOGGLE_PLAY' });
    });
    
    return () => {
      audio.removeEventListener('timeupdate', updateTime);
      audio.removeEventListener('loadedmetadata', updateDuration);
    };
  }, [audio, dispatch]);

  useEffect(() => {
    audio.volume = volume;
  }, [audio, volume]);

  useEffect(() => {
    if (state.currentSong) {
      if (state.currentSong.file_path) {
        audio.src = `${BACKEND_URL}${state.currentSong.file_path}`;
      } else if (state.currentSong.external_url) {
        audio.src = state.currentSong.external_url;
      }
      audio.load();
    }
  }, [state.currentSong, audio]);

  useEffect(() => {
    if (state.isPlaying && state.currentSong) {
      audio.play().catch(console.error);
    } else {
      audio.pause();
    }
  }, [state.isPlaying, audio, state.currentSong]);

  const handlePlayPause = () => {
    if (state.currentSong) {
      dispatch({ type: 'TOGGLE_PLAY' });
    }
  };

  const handleSongSelect = (song) => {
    if (!state.isLive) {
      dispatch({ type: 'SET_CURRENT_SONG', payload: song });
      dispatch({ type: 'TOGGLE_PLAY' });
    }
  };

  const formatTime = (time) => {
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  return (
    <div className="station-listen">
      {/* Audio Player */}
      <div className="audio-player">
        {state.currentSong ? (
          <>
            <div className="song-info">
              {state.currentSong.artwork_url && (
                <img 
                  src={`${BACKEND_URL}${state.currentSong.artwork_url}`} 
                  alt="Album artwork"
                  className="album-art"
                />
              )}
              <div className="song-details">
                <h3>{state.currentSong.title}</h3>
                <p>{state.currentSong.artist_name}</p>
                {state.currentSong.genre && <span className="genre">{state.currentSong.genre}</span>}
                {state.isLive && <span className="live-indicator-small">🔴 LIVE</span>}
              </div>
            </div>
            
            <div className="player-controls">
              <button 
                className={`play-btn ${state.isPlaying ? 'playing' : ''}`}
                onClick={handlePlayPause}
                disabled={state.isLive}
              >
                {state.isPlaying ? '⏸️' : '▶️'}
              </button>
              
              <div className="progress-section">
                <span className="time">{formatTime(currentTime)}</span>
                <div className="progress-bar">
                  <div 
                    className="progress-fill"
                    style={{ width: duration ? `${(currentTime / duration) * 100}%` : '0%' }}
                  />
                </div>
                <span className="time">{formatTime(duration)}</span>
              </div>
              
              <div className="volume-control">
                <span>🔊</span>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  value={volume}
                  onChange={(e) => setVolume(parseFloat(e.target.value))}
                  className="volume-slider"
                />
              </div>
            </div>
          </>
        ) : (
          <div className="no-song">
            <h3>🎵 Welcome to {state.currentStation?.name}</h3>
            <p>Select a song to start listening or wait for a live broadcast</p>
          </div>
        )}
      </div>

      {/* Station Music Library */}
      <div className="station-music-library">
        <h2>🎵 Station Music Library</h2>
        {state.isLive && (
          <div className="live-notice">
            🔴 Live broadcast in progress - Playback controlled by DJ
          </div>
        )}
        
        <div className="songs-grid">
          {state.stationSongs.map(song => (
            <div 
              key={song.id} 
              className={`song-card ${state.currentSong?.id === song.id ? 'active' : ''} ${state.isLive ? 'live-mode' : ''}`}
              onClick={() => handleSongSelect(song)}
            >
              {song.artwork_url && (
                <img 
                  src={`${BACKEND_URL}${song.artwork_url}`} 
                  alt="Album artwork"
                  className="song-artwork"
                />
              )}
              <div className="song-info-card">
                <h4>{song.title}</h4>
                <p>{song.artist_name}</p>
                {song.genre && <span className="genre-tag">{song.genre}</span>}
              </div>
              <button 
                className={`play-button ${state.isLive ? 'disabled' : ''}`}
                disabled={state.isLive}
              >
                {state.isLive ? '🔴' : (state.currentSong?.id === song.id && state.isPlaying ? '⏸️' : '▶️')}
              </button>
            </div>
          ))}
        </div>
        
        {state.stationSongs.length === 0 && (
          <div className="no-songs">
            <h3>No music yet</h3>
            <p>This station is just getting started. Check back soon for new music!</p>
          </div>
        )}
      </div>
    </div>
  );
}

// Station Upload Tab
function StationUpload() {
  const { stationSlug } = useParams();
  const { state } = useRadio();
  const [formData, setFormData] = useState({
    title: '',
    artist_name: '',
    genre: ''
  });
  const [audioFile, setAudioFile] = useState(null);
  const [artworkFile, setArtworkFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploaded, setUploaded] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!audioFile) {
      alert('Please select an audio file');
      return;
    }
    
    setIsUploading(true);
    
    const uploadData = new FormData();
    uploadData.append('title', formData.title);
    uploadData.append('artist_name', formData.artist_name);
    uploadData.append('genre', formData.genre);
    uploadData.append('audio_file', audioFile);
    if (artworkFile) {
      uploadData.append('artwork_file', artworkFile);
    }
    
    try {
      await axios.post(`${API}/stations/${stationSlug}/songs/upload`, uploadData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });
      setUploaded(true);
      setFormData({ title: '', artist_name: '', genre: '' });
      setAudioFile(null);
      setArtworkFile(null);
    } catch (error) {
      console.error('Error uploading song:', error);
      alert('Error uploading song. Please try again.');
    } finally {
      setIsUploading(false);
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  if (uploaded) {
    return (
      <div className="upload-success">
        <h2>🎵 Upload Successful!</h2>
        <p>Your song has been uploaded to {state.currentStation?.name} and is pending approval.</p>
        <button onClick={() => setUploaded(false)} className="upload-another-btn">
          Upload Another Song
        </button>
      </div>
    );
  }

  return (
    <div className="station-upload">
      <div className="upload-header">
        <h2>🎵 Add Music to {state.currentStation?.name}</h2>
        <p>Upload your music to this station</p>
      </div>
      
      {state.isAuthenticated ? (
        <form onSubmit={handleSubmit} className="upload-form">
          <div className="form-group">
            <label htmlFor="title">Song Title *</label>
            <input
              type="text"
              id="title"
              name="title"
              value={formData.title}
              onChange={handleInputChange}
              required
              placeholder="Name of your song"
            />
          </div>
          
          <div className="form-group">
            <label htmlFor="artist_name">Artist Name *</label>
            <input
              type="text"
              id="artist_name"
              name="artist_name"
              value={formData.artist_name}
              onChange={handleInputChange}
              required
              placeholder="Your artist or band name"
            />
          </div>
          
          <div className="form-group">
            <label htmlFor="genre">Genre</label>
            <select
              id="genre"
              name="genre"
              value={formData.genre}
              onChange={handleInputChange}
            >
              <option value="">Select Genre</option>
              <option value="Indie Rock">Indie Rock</option>
              <option value="Indie Pop">Indie Pop</option>
              <option value="Alternative">Alternative</option>
              <option value="Folk">Folk</option>
              <option value="Electronic">Electronic</option>
              <option value="Hip Hop">Hip Hop</option>
              <option value="R&B">R&B</option>
              <option value="Jazz">Jazz</option>
              <option value="Other">Other</option>
            </select>
          </div>
          
          <div className="form-group">
            <label htmlFor="audio_file">Audio File * (MP3, WAV)</label>
            <input
              type="file"
              id="audio_file"
              accept=".mp3,.wav,.m4a"
              onChange={(e) => setAudioFile(e.target.files[0])}
              required
              className="file-input"
            />
          </div>
          
          <div className="form-group">
            <label htmlFor="artwork_file">Artwork (optional)</label>
            <input
              type="file"
              id="artwork_file"
              accept=".jpg,.jpeg,.png"
              onChange={(e) => setArtworkFile(e.target.files[0])}
              className="file-input"
            />
          </div>
          
          <button 
            type="submit" 
            disabled={isUploading}
            className="upload-btn"
          >
            {isUploading ? '⏳ Uploading...' : '🎵 Upload to Station'}
          </button>
        </form>
      ) : (
        <div className="please-login">
          <p>Please sign in to upload music to this station</p>
        </div>
      )}
    </div>
  );
}

// Station Management Tab (for station owners)
function StationManage() {
  const { stationSlug } = useParams();
  const { state, socket } = useRadio();
  const [streamTitle, setStreamTitle] = useState('');
  const [streamDescription, setStreamDescription] = useState('');
  const [isStartingStream, setIsStartingStream] = useState(false);

  const startLiveStream = async () => {
    if (!streamTitle.trim()) {
      alert('Please enter a stream title');
      return;
    }
    
    setIsStartingStream(true);
    try {
      await axios.post(`${API}/stations/${stationSlug}/live/start`, {
        title: streamTitle,
        description: streamDescription
      });
      setStreamTitle('');
      setStreamDescription('');
    } catch (error) {
      console.error('Error starting stream:', error);
      alert('Failed to start live stream');
    } finally {
      setIsStartingStream(false);
    }
  };

  const stopLiveStream = async () => {
    try {
      await axios.post(`${API}/stations/${stationSlug}/live/stop`);
    } catch (error) {
      console.error('Error stopping stream:', error);
    }
  };

  const djControl = (action, data = {}) => {
    if (socket) {
      socket.send(JSON.stringify({
        type: 'dj_control',
        action,
        data,
        username: state.currentUser.username
      }));
    }
  };

  const playSelectedSong = (song) => {
    djControl('play', { song });
  };

  return (
    <div className="station-manage">
      <div className="manage-header">
        <h2>🎙️ Manage {state.currentStation?.name}</h2>
        <p>Control your station's live broadcasts</p>
      </div>
      
      <div className="live-stream-controls">
        <h3>Live Stream Controls</h3>
        {!state.isLive ? (
          <div className="start-stream-form">
            <div className="form-group">
              <label>Stream Title</label>
              <input
                type="text"
                value={streamTitle}
                onChange={(e) => setStreamTitle(e.target.value)}
                placeholder="Enter your show title"
              />
            </div>
            <div className="form-group">
              <label>Description (optional)</label>
              <textarea
                value={streamDescription}
                onChange={(e) => setStreamDescription(e.target.value)}
                placeholder="Describe your show..."
                rows="3"
              />
            </div>
            <button 
              onClick={startLiveStream}
              disabled={isStartingStream}
              className="start-stream-btn"
            >
              {isStartingStream ? '⏳ Starting...' : '🎙️ Go Live'}
            </button>
          </div>
        ) : (
          <div className="live-controls">
            <div className="live-status">
              <div className="live-badge large">
                <span className="live-dot"></span>
                LIVE ON AIR
              </div>
              <p>Broadcasting to {state.currentStation?.current_listeners} listeners</p>
            </div>
            <button onClick={stopLiveStream} className="stop-stream-btn">
              📴 End Stream
            </button>
          </div>
        )}
      </div>
      
      <div className="station-music-controls">
        <h3>Broadcast Music</h3>
        <div className="dj-song-grid">
          {state.stationSongs.map(song => (
            <div key={song.id} className="dj-song-card">
              {song.artwork_url && (
                <img 
                  src={`${BACKEND_URL}${song.artwork_url}`} 
                  alt="Album artwork"
                  className="song-artwork-small"
                />
              )}
              <div className="dj-song-info">
                <h4>{song.title}</h4>
                <p>{song.artist_name}</p>
                {song.genre && <span className="genre-tag">{song.genre}</span>}
              </div>
              <button 
                onClick={() => playSelectedSong(song)}
                className="dj-play-btn"
                disabled={!state.isLive}
              >
                📻 Broadcast
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// Notifications
function Notifications() {
  const { state, dispatch } = useRadio();
  
  useEffect(() => {
    state.notifications.forEach(notification => {
      const timer = setTimeout(() => {
        dispatch({ type: 'REMOVE_NOTIFICATION', payload: notification.id });
      }, 5000);
      
      return () => clearTimeout(timer);
    });
  }, [state.notifications, dispatch]);
  
  if (state.notifications.length === 0) return null;
  
  return (
    <div className="notifications">
      {state.notifications.map(notification => (
        <div 
          key={notification.id} 
          className={`notification ${notification.type}`}
          onClick={() => dispatch({ type: 'REMOVE_NOTIFICATION', payload: notification.id })}
        >
          {notification.message}
        </div>
      ))}
    </div>
  );
}

// Main App Component
function AppContent() {
  return (
    <div className="App">
      <PlatformHeader />
      <Notifications />
      
      <Routes>
        <Route path="/" element={<StationDiscovery />} />
        <Route path="/create-station" element={<CreateStation />} />
        <Route path="/station/:stationSlug" element={<StationPage />} />
      </Routes>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <RadioProvider>
        <AppContent />
      </RadioProvider>
    </BrowserRouter>
  );
}

export default App;