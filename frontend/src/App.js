import React, { useState, useEffect, createContext, useContext, useReducer } from 'react';
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
  playlist: [],
  isPlaying: false,
  currentUser: null,
  isAuthenticated: false,
  token: localStorage.getItem('token'),
  songs: [],
  artists: [],
  playlists: [],
  schedule: [],
  currentShow: null,
  liveStream: null,
  isLive: false,
  notifications: []
};

function radioReducer(state, action) {
  switch (action.type) {
    case 'SET_SONGS':
      return { ...state, songs: action.payload };
    case 'SET_ARTISTS':
      return { ...state, artists: action.payload };
    case 'SET_PLAYLISTS':
      return { ...state, playlists: action.payload };
    case 'SET_SCHEDULE':
      return { ...state, schedule: action.payload };
    case 'SET_CURRENT_SHOW':
      return { ...state, currentShow: action.payload };
    case 'SET_LIVE_STREAM':
      return { ...state, liveStream: action.payload };
    case 'SET_CURRENT_SONG':
      return { ...state, currentSong: action.payload };
    case 'SET_PLAYLIST':
      return { ...state, playlist: action.payload };
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

  // WebSocket connection
  useEffect(() => {
    const connectWebSocket = () => {
      const wsUrl = state.token 
        ? `${WS_URL}/api/ws/general?token=${state.token}`
        : `${WS_URL}/api/ws/general`;
      
      const ws = new WebSocket(wsUrl);
      
      ws.onopen = () => {
        console.log('WebSocket connected');
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
            dispatch({ 
              type: 'ADD_NOTIFICATION', 
              payload: { 
                message: `📴 ${data.dj_name} ended their live stream`, 
                type: 'info' 
              } 
            });
            break;
          case 'song_upload':
            if (state.currentUser?.role === 'dj' || state.currentUser?.role === 'admin') {
              dispatch({ 
                type: 'ADD_NOTIFICATION', 
                payload: { 
                  message: `🎵 New song uploaded: ${data.song.title}`, 
                  type: 'success' 
                } 
              });
            }
            break;
          case 'artist_submission':
            if (state.currentUser?.role === 'dj' || state.currentUser?.role === 'admin') {
              dispatch({ 
                type: 'ADD_NOTIFICATION', 
                payload: { 
                  message: `🎤 New artist submission: ${data.artist.name}`, 
                  type: 'info' 
                } 
              });
            }
            break;
          case 'dj_control':
            // Handle DJ control messages for synchronized playback
            if (data.action === 'play' && data.data.song) {
              dispatch({ type: 'SET_CURRENT_SONG', payload: data.data.song });
              dispatch({ type: 'TOGGLE_PLAY', payload: true });
            }
            break;
          case 'chat_message':
            // Handle chat messages
            break;
          default:
            break;
        }
      };
      
      ws.onclose = () => {
        console.log('WebSocket disconnected');
        setSocket(null);
        // Reconnect after 3 seconds
        setTimeout(connectWebSocket, 3000);
      };
      
      return ws;
    };

    const ws = connectWebSocket();
    
    return () => {
      if (ws) ws.close();
    };
  }, [state.token, state.currentUser]);

  // Load initial data
  useEffect(() => {
    loadSongs();
    loadArtists();
    loadPlaylists();
    loadSchedule();
    loadCurrentShow();
    loadLiveStatus();
  }, []);

  const loadSongs = async () => {
    try {
      const response = await axios.get(`${API}/songs?approved_only=true`);
      dispatch({ type: 'SET_SONGS', payload: response.data });
    } catch (error) {
      console.error('Error loading songs:', error);
    }
  };

  const loadArtists = async () => {
    try {
      const response = await axios.get(`${API}/artists?approved_only=true`);
      dispatch({ type: 'SET_ARTISTS', payload: response.data });
    } catch (error) {
      console.error('Error loading artists:', error);
    }
  };

  const loadPlaylists = async () => {
    try {
      const response = await axios.get(`${API}/playlists`);
      dispatch({ type: 'SET_PLAYLISTS', payload: response.data });
    } catch (error) {
      console.error('Error loading playlists:', error);
    }
  };

  const loadSchedule = async () => {
    try {
      const response = await axios.get(`${API}/schedule`);
      dispatch({ type: 'SET_SCHEDULE', payload: response.data });
    } catch (error) {
      console.error('Error loading schedule:', error);
    }
  };

  const loadCurrentShow = async () => {
    try {
      const response = await axios.get(`${API}/schedule/now`);
      if (response.data.id) {
        dispatch({ type: 'SET_CURRENT_SHOW', payload: response.data });
      }
    } catch (error) {
      console.error('Error loading current show:', error);
    }
  };

  const loadLiveStatus = async () => {
    try {
      const response = await axios.get(`${API}/live/status`);
      if (response.data.id) {
        dispatch({ type: 'SET_LIVE_STREAM', payload: response.data });
        dispatch({ type: 'SET_LIVE_STATUS', payload: true });
      }
    } catch (error) {
      console.error('Error loading live status:', error);
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

  const value = {
    state,
    dispatch,
    socket,
    loadSongs,
    loadArtists,
    loadPlaylists,
    loadSchedule,
    loadCurrentShow,
    loadLiveStatus,
    login,
    register,
    logout
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

// Authentication Component
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
          <h2>{isLogin ? '🎵 Sign In' : '🎤 Join the Station'}</h2>
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
            {isSubmitting ? '⏳ Processing...' : (isLogin ? '🎵 Sign In' : '🚀 Join Station')}
          </button>
        </form>
        
        <div className="auth-switch">
          {isLogin ? (
            <p>New to the station? <button onClick={onSwitch}>Create Account</button></p>
          ) : (
            <p>Already have an account? <button onClick={onSwitch}>Sign In</button></p>
          )}
        </div>
      </div>
    </div>
  );
}

// Header Component
function Header() {
  const { state, logout } = useRadio();
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [isLogin, setIsLogin] = useState(true);
  
  return (
    <header className="header">
      <div className="header-content">
        <div className="logo">
          <h1>🎵 Indie Music Station</h1>
        </div>
        <div className="live-indicator">
          {state.isLive && state.liveStream && (
            <div className="live-badge">
              <span className="live-dot"></span>
              LIVE: {state.liveStream.dj_name}
            </div>
          )}
        </div>
        <div className="user-info">
          {state.isAuthenticated ? (
            <div className="user-actions">
              <span>Welcome, {state.currentUser.username}</span>
              <span className={`role-badge ${state.currentUser.role}`}>
                {state.currentUser.role}
              </span>
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
                Join Station
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

// DJ Dashboard Component
function DJDashboard() {
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
      await axios.post(`${API}/live/start`, {
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
      await axios.post(`${API}/live/stop`);
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
    <div className="dj-dashboard">
      <div className="dj-header">
        <h2>🎙️ DJ Dashboard</h2>
        <p>Control your live broadcast</p>
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
              <p>Broadcasting: {state.liveStream?.title}</p>
            </div>
            <button onClick={stopLiveStream} className="stop-stream-btn">
              📴 End Stream
            </button>
          </div>
        )}
      </div>
      
      <div className="dj-music-controls">
        <h3>Music Library Control</h3>
        <div className="dj-song-grid">
          {state.songs.map(song => (
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

// Audio Player Component
function AudioPlayer() {
  const { state, dispatch } = useRadio();
  const [audio] = useState(new Audio());
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);

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

  const handleSeek = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const percent = (e.clientX - rect.left) / rect.width;
    const newTime = percent * duration;
    audio.currentTime = newTime;
    setCurrentTime(newTime);
  };

  const formatTime = (time) => {
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  if (!state.currentSong) {
    return (
      <div className="audio-player no-song">
        <div className="player-info">
          <h3>🎵 Ready to Play</h3>
          <p>Select a song from our indie collection or listen to live broadcasts</p>
        </div>
      </div>
    );
  }

  return (
    <div className="audio-player">
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
        >
          {state.isPlaying ? '⏸️' : '▶️'}
        </button>
        
        <div className="progress-section">
          <span className="time">{formatTime(currentTime)}</span>
          <div className="progress-bar" onClick={handleSeek}>
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
    </div>
  );
}

// Song List Component (Listeners can only browse and play, not control broadcasts)
function SongList() {
  const { state, dispatch } = useRadio();
  const [filter, setFilter] = useState('');
  const [selectedGenre, setSelectedGenre] = useState('');

  const filteredSongs = state.songs.filter(song => {
    const matchesFilter = song.title.toLowerCase().includes(filter.toLowerCase()) ||
                         song.artist_name.toLowerCase().includes(filter.toLowerCase());
    const matchesGenre = !selectedGenre || song.genre === selectedGenre;
    return matchesFilter && matchesGenre;
  });

  const genres = [...new Set(state.songs.map(song => song.genre).filter(Boolean))];

  const handleSongSelect = (song) => {
    // Only allow song selection if user is not in a live broadcast
    if (!state.isLive) {
      dispatch({ type: 'SET_CURRENT_SONG', payload: song });
      dispatch({ type: 'TOGGLE_PLAY' });
    }
  };

  return (
    <div className="song-list-section">
      <div className="section-header">
        <h2>🎵 Music Library</h2>
        {state.isLive && (
          <div className="live-notice">
            🔴 Live broadcast in progress - Playback controlled by DJ
          </div>
        )}
        <div className="filters">
          <input
            type="text"
            placeholder="Search songs or artists..."
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
      
      <div className="song-grid">
        {filteredSongs.map(song => (
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
      
      {filteredSongs.length === 0 && (
        <div className="no-results">
          <h3>No songs found</h3>
          <p>Try adjusting your search or filter criteria</p>
        </div>
      )}
    </div>
  );
}

// Artist Submission Form (unchanged)
function ArtistSubmissionForm() {
  const [formData, setFormData] = useState({
    name: '',
    bio: '',
    email: '',
    social_links: {}
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    
    try {
      await axios.post(`${API}/artists/submit`, formData);
      setSubmitted(true);
      setFormData({ name: '', bio: '', email: '', social_links: {} });
    } catch (error) {
      console.error('Error submitting artist:', error);
      alert('Error submitting artist information. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  if (submitted) {
    return (
      <div className="submission-success">
        <h2>✅ Submission Received!</h2>
        <p>Thank you for your artist submission. We'll review your information and get back to you soon.</p>
        <button onClick={() => setSubmitted(false)} className="submit-another-btn">
          Submit Another Artist
        </button>
      </div>
    );
  }

  return (
    <div className="artist-submission-form">
      <div className="form-header">
        <h2>🎤 Artist Submission</h2>
        <p>Share your music with our indie community</p>
      </div>
      
      <form onSubmit={handleSubmit} className="submission-form">
        <div className="form-group">
          <label htmlFor="name">Artist Name *</label>
          <input
            type="text"
            id="name"
            name="name"
            value={formData.name}
            onChange={handleInputChange}
            required
            placeholder="Your stage or band name"
          />
        </div>
        
        <div className="form-group">
          <label htmlFor="email">Email *</label>
          <input
            type="email"
            id="email"
            name="email"
            value={formData.email}
            onChange={handleInputChange}
            required
            placeholder="your@email.com"
          />
        </div>
        
        <div className="form-group">
          <label htmlFor="bio">Bio</label>
          <textarea
            id="bio"
            name="bio"
            value={formData.bio}
            onChange={handleInputChange}
            placeholder="Tell us about your music, influences, and story..."
            rows="4"
          />
        </div>
        
        <button 
          type="submit" 
          disabled={isSubmitting}
          className="submit-btn"
        >
          {isSubmitting ? '⏳ Submitting...' : '📤 Submit Artist Info'}
        </button>
      </form>
    </div>
  );
}

// Song Upload Form
function SongUploadForm() {
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
      await axios.post(`${API}/songs/upload`, uploadData, {
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
        <p>Your song has been uploaded and is pending approval. Thank you for sharing your music!</p>
        <button onClick={() => setUploaded(false)} className="upload-another-btn">
          Upload Another Song
        </button>
      </div>
    );
  }

  return (
    <div className="song-upload-form">
      <div className="form-header">
        <h2>🎵 Upload Your Song</h2>
        <p>Share your music with the indie community</p>
        {!state.isAuthenticated && (
          <div className="auth-notice">
            <p>⚠️ Please sign in to upload music</p>
          </div>
        )}
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
            {isUploading ? '⏳ Uploading...' : '🎵 Upload Song'}
          </button>
        </form>
      ) : (
        <div className="please-login">
          <p>Please sign in to upload music to the station</p>
        </div>
      )}
    </div>
  );
}

// Current Show Info
function CurrentShowInfo() {
  const { state } = useRadio();
  
  if (state.isLive && state.liveStream) {
    return (
      <div className="current-show live">
        <div className="show-info">
          <h3>🎙️ {state.liveStream.title}</h3>
          <p>with DJ {state.liveStream.dj_name}</p>
          {state.liveStream.description && (
            <p className="show-description">{state.liveStream.description}</p>
          )}
        </div>
        <div className="live-indicator-large">
          <span className="live-dot"></span>
          LIVE ON AIR
        </div>
      </div>
    );
  }
  
  if (state.currentShow) {
    return (
      <div className="current-show">
        <div className="show-info">
          <h3>🎙️ {state.currentShow.title}</h3>
          <p>with DJ {state.currentShow.dj_name}</p>
          {state.currentShow.description && (
            <p className="show-description">{state.currentShow.description}</p>
          )}
          <div className="show-time">
            {new Date(state.currentShow.start_time).toLocaleTimeString()} - 
            {new Date(state.currentShow.end_time).toLocaleTimeString()}
          </div>
        </div>
      </div>
    );
  }
  
  return (
    <div className="current-show no-show">
      <h3>🎵 Automated Programming</h3>
      <p>Enjoy our curated indie music collection</p>
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
function App() {
  const [currentTab, setCurrentTab] = useState('listen');
  const { state } = useRadio();
  
  const canAccessDJFeatures = state.isAuthenticated && 
    (state.currentUser?.role === 'dj' || state.currentUser?.role === 'admin');
  
  return (
    <RadioProvider>
      <div className="App">
        <Header />
        <Notifications />
        
        <nav className="main-nav">
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
            📤 Upload Music
          </button>
          <button 
            className={currentTab === 'submit' ? 'active' : ''}
            onClick={() => setCurrentTab('submit')}
          >
            🎤 Submit Artist
          </button>
          {canAccessDJFeatures && (
            <button 
              className={currentTab === 'dj' ? 'active' : ''}
              onClick={() => setCurrentTab('dj')}
            >
              🎙️ DJ Dashboard
            </button>
          )}
        </nav>
        
        <main className="main-content">
          {currentTab === 'listen' && (
            <div className="listen-section">
              <CurrentShowInfo />
              <AudioPlayer />
              <SongList />
            </div>
          )}
          
          {currentTab === 'upload' && <SongUploadForm />}
          {currentTab === 'submit' && <ArtistSubmissionForm />}
          {currentTab === 'dj' && canAccessDJFeatures && <DJDashboard />}
        </main>
        
        <footer className="footer">
          <p>🎵 Indie Music Station - Supporting Local Artists Since 2024</p>
        </footer>
      </div>
    </RadioProvider>
  );
}

export default App;