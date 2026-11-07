import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { PieChart, Pie, Cell, LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { AlertTriangle, AlertCircle, Phone, Mail, Camera, Activity, FileText } from 'lucide-react';
import './index.css';

const App = () => {
  const [screen, setScreen] = useState('login'); 
  const [deviceIp, setDeviceIp] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [authError, setAuthError] = useState('');
  const [token, setToken] = useState(null);
  
  const [isLiveViewOpen, setIsLiveViewOpen] = useState(false);
  const [isWipeModalOpen, setIsWipeModalOpen] = useState(false);
  const [wipeUser, setWipeUser] = useState('');
  const [wipePass, setWipePass] = useState('');
  const [actionAlert, setActionAlert] = useState(null);
  const [emergencyAlert, setEmergencyAlert] = useState(null);
  const [events, setEvents] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [overrideMode, setOverrideMode] = useState('AUTO');
  const [mosfetMode, setMosfetMode] = useState('AUTO');

  // Track the highest event ID we have already shown the emergency overlay for
  const lastSeenEmergencyId = useRef(null);

  // Stats derived from events
  const criticalEvents = events.filter(e => e.risk_level === 'Critical' || e.event_type === 'X_GESTURE_EMERGENCY' || e.event_type === 'ACCIDENT_DETECTED');
  const emergencyEvents = events.filter(e => e.risk_level === 'High');
  const riskEvents = events.filter(e => e.risk_level === 'Medium' || e.risk_level === 'Low');

  // Categorise event for display color
  const getEventStyle = (ev) => {
    if (ev.event_type === 'X_GESTURE_EMERGENCY') return { border: '2px solid #ff2a6d', bg: 'rgba(255,42,109,0.08)', color: '#ff2a6d' };
    if (ev.event_type === 'ACCIDENT_DETECTED') return { border: '2px solid #0080ff', bg: 'rgba(0,128,255,0.08)', color: '#0080ff' };
    if (ev.event_type === 'RAPID_MOTION' || ev.activity === 'RUNNING') return { border: '2px solid #f39c12', bg: 'rgba(243,156,18,0.08)', color: '#f39c12' };
    if (ev.event_type === 'SUSPICIOUS_ACTIVITY') return { border: '2px solid #9b59b6', bg: 'rgba(155,89,182,0.08)', color: '#9b59b6' };
    if (ev.emotion_group === 'Fear') return { border: '2px solid #e74c3c', bg: 'rgba(231,76,60,0.08)', color: '#e74c3c' };
    if (ev.emotion_group === 'Angry') return { border: '2px solid #e67e22', bg: 'rgba(230,126,34,0.08)', color: '#e67e22' };
    if (ev.emotion_group === 'Sad') return { border: '2px solid #3498db', bg: 'rgba(52,152,219,0.08)', color: '#3498db' };
    return { border: '1px solid #444', bg: 'transparent', color: '#aaa' };
  };

  // Backend config
  const API_BASE = 'http://localhost:5000/api'; // Or relative if served via backend

  const handleLogin = async (e) => {
    e.preventDefault();
    setAuthError('');
    setIsLoading(true);
    
    try {
      const data = new URLSearchParams();
      data.append('username', username);
      data.append('password', password);
      
      // Hit actual backend endpoint deployed in Phase 2
      const res = await axios.post(`${API_BASE}/auth/login`, data);
      setToken(res.data.access_token);
      axios.defaults.headers.common['Authorization'] = `Bearer ${res.data.access_token}`;
      setScreen('connect');
    } catch (err) {
      // Fallback to hardcoded if backend is unreachable 
      if (username === 'karthi' && password === 'karthi8825') {
        setScreen('connect'); // Just bypass for edge Pi testing if backend isn't up
      } else {
        setAuthError('Invalid credentials or backend unreachable.');
      }
    }
    setIsLoading(false);
  };

  const handleWipe = async (e) => {
    e.preventDefault();
    try {
        const data = new URLSearchParams();
        data.append('username', wipeUser.trim());
        data.append('password', wipePass.trim());
        const res = await axios.post(`${API_BASE}/admin/emergency-wipe`, data);
        if (res.data.success) {
            setIsWipeModalOpen(false);
            setWipeUser('');
            setWipePass('');
            fetchEvents();
            alert('System Wipe Successful.');
        }
    } catch (err) {
        alert('Invalid Management Credentials.');
    }
  };

  const handleConnect = async (e) => {
    e.preventDefault();
    if (!deviceIp.trim()) return;
    
    setAuthError('');
    setIsLoading(true);

    try {
      if (token) {
        const data = new URLSearchParams();
        data.append('ip_address', deviceIp);
        const res = await axios.post(`${API_BASE}/device/verify`, data);
        
        if (res.data.success) {
          setScreen('dashboard');
          fetchEvents();
        } else {
          setAuthError(res.data.message || 'Device unreachable');
        }
      } else {
        // Fallback demo map (if backend bypassed)
        setScreen('dashboard');
      }
    } catch (err) {
      setAuthError('Error pinging device');
    }
    setIsLoading(false);
  };

  const fetchEvents = async () => {
    try {
      const res = await axios.get(`${API_BASE}/events?limit=150`);
      if (res.data.success) {
        setEvents(res.data.events);
      }
    } catch (err) {
      console.error("Failed to fetch events:", err);
    }
    
    // Also fetch the current override mode
    try {
      const modeRes = await axios.get(`${API_BASE}/device/mode?tower_id=TOWER-01`);
      if (modeRes.data) {
        if (modeRes.data.mode) setOverrideMode(modeRes.data.mode);
        if (modeRes.data.mosfet_mode) setMosfetMode(modeRes.data.mosfet_mode);
      }
    } catch (err) {
      console.error("Failed to fetch override mode:", err);
    }
  };

  const handleModeChange = async (newMode) => {
    setOverrideMode(newMode); // Optimistic UI update
    try {
      await axios.post(`${API_BASE}/device/mode`, { tower_id: 'TOWER-01', mode: newMode });
    } catch (err) {
      console.error("Failed to update override mode:", err);
    }
  };

  const handleMosfetChange = async (newMode) => {
    setMosfetMode(newMode); // Optimistic UI update
    try {
      await axios.post(`${API_BASE}/device/mode`, { tower_id: 'TOWER-01', mosfet_mode: newMode });
    } catch (err) {
      console.error("Failed to update mosfet mode:", err);
    }
  };

  // Auto-refresh events
  useEffect(() => {
    let interval;
    if (screen === 'dashboard') {
      fetchEvents();
      interval = setInterval(fetchEvents, 2000);
    }
    return () => clearInterval(interval);
  }, [screen]);

  // Watch for Critical events and auto-trigger emergency overlay
  // Uses a ref-based ID tracker — immune to timezone offset bugs.
  useEffect(() => {
    if (events.length === 0) return;
    const latest = events[0]; // Backend returns newest first
    const isCritical =
      latest.event_type === 'X_GESTURE_EMERGENCY' ||
      latest.event_type === 'ACCIDENT_DETECTED';
    
    // Only fire if this is a NEW event we haven't shown yet
    if (isCritical && latest.id !== lastSeenEmergencyId.current) {
      lastSeenEmergencyId.current = latest.id;
      setEmergencyAlert(latest);
    }
  }, [events]);

  // --- Graph Data ---
  const pieData = [
    { name: 'Emergency', value: emergencyEvents.length, color: '#ff2a6d' },
    { name: 'Risk', value: riskEvents.length, color: '#f39c12' }
  ];

  // Aggregates alerts in 5-minute bins for the last 60 minutes
  const getLineData = () => {
    const bins = {};
    const now = new Date();
    
    // 1. Initialize 12 slots (60 mins total / 5 mins per slot)
    for (let i = 0; i < 12; i++) {
        const d = new Date(now.getTime() - i * 5 * 60 * 1000);
        const minutes = Math.floor(d.getMinutes() / 5) * 5;
        const timeKey = `${d.getHours().toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
        bins[timeKey] = 0;
    }
    
    // 2. Aggregate actual events
    events.forEach(e => {
        const d = new Date(e.created_at);
        const diffMs = now - d;
        // Only count if within the last hour
        if (diffMs > 0 && diffMs < 60 * 60 * 1000) {
            const minutes = Math.floor(d.getMinutes() / 5) * 5;
            const timeKey = `${d.getHours().toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
            if (bins[timeKey] !== undefined) {
                bins[timeKey]++;
            }
        }
    });

    // 3. Return sorted data points
    return Object.keys(bins).sort().map(k => ({ time: k, alerts: bins[k] }));
  };

  return (
    <div className="app-container">
      {screen === 'login' && (
        <div className="modal-overlay">
          <div className="glass-panel animate-slide-up" style={{ width: '400px', textAlign: 'center' }}>
            <h2 className="gradient-text" style={{ marginBottom: '8px' }}>Smart Tower Edge AI</h2>
            <p style={{ color: 'var(--text-muted)', marginBottom: '24px' }}>Welcome back, Operator</p>
            
            <form onSubmit={handleLogin}>
              <div style={{ marginBottom: '16px' }}>
                <input 
                  type="text" 
                  className="input-field" 
                  placeholder="Username" 
                  value={username}
                  onChange={e => setUsername(e.target.value)}
                  required
                />
              </div>
              <div style={{ marginBottom: '24px' }}>
                <input 
                  type="password" 
                  className="input-field" 
                  placeholder="Password" 
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  required
                />
              </div>
              {authError && <p style={{ color: 'var(--neon-magenta)', marginBottom: '16px', fontSize: '0.9rem' }}>{authError}</p>}
              <button type="submit" className="btn-primary" disabled={isLoading}>
                {isLoading ? 'Authenticating...' : 'Secure Login'}
              </button>
            </form>
          </div>
        </div>
      )}

      {screen === 'connect' && (
        <div className="modal-overlay">
          <div className="glass-panel animate-slide-up" style={{ width: '400px', textAlign: 'center' }}>
            <h2 className="gradient-text" style={{ marginBottom: '8px' }}>Verifying Edge Node</h2>
            <p style={{ color: 'var(--text-muted)', marginBottom: '24px' }}>Enter the IP address of the local Pi Node to ping.</p>
            
            <form onSubmit={handleConnect}>
              <div style={{ marginBottom: '24px' }}>
                <input 
                  type="text" 
                  className="input-field" 
                  placeholder="e.g. 192.168.1.55" 
                  value={deviceIp}
                  onChange={e => setDeviceIp(e.target.value)}
                  required
                />
              </div>
              {authError && <p style={{ color: 'var(--neon-magenta)', marginBottom: '16px', fontSize: '0.9rem' }}>{authError}</p>}
              <button type="submit" className="btn-primary" disabled={isLoading}>
                {isLoading ? 'Pinging Device...' : 'Verify Device SSH / Ping'}
              </button>
            </form>
          </div>
        </div>
      )}

      {screen === 'dashboard' && (
        <div className="animate-slide-up" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          <header className="header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <h2 className="gradient-text">Master Command Dashboard</h2>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Secure Link Established with Pi: {deviceIp}</p>
            </div>
            
            <div style={{ display: 'flex', gap: '20px', alignItems: 'center' }}>
              <div className="status-badge status-online" style={{ marginRight: '10px' }}>
                <div className="status-dot"></div>
                DEVICE ONLINE
              </div>
              
              <div style={{ display: 'flex', alignItems: 'center', background: '#222', borderRadius: '4px', padding: '4px 8px', border: '1px solid #444' }}>
                <span style={{ fontSize: '0.8rem', color: '#ccc', marginRight: '8px' }}>Edge Mode:</span>
                <select 
                  value={overrideMode} 
                  onChange={(e) => handleModeChange(e.target.value)}
                  style={{ background: '#111', color: 'white', border: '1px solid #555', borderRadius: '4px', padding: '4px', fontSize: '0.8rem' }}
                >
                  <option value="AUTO">🤖 Auto (LDR)</option>
                  <option value="DAY">☀️ Force Day</option>
                  <option value="NIGHT">🌙 Force Night</option>
                </select>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', background: '#222', borderRadius: '4px', padding: '4px 8px', border: '1px solid #444' }}>
                <span style={{ fontSize: '0.8rem', color: '#ccc', marginRight: '8px' }}>Mosfet:</span>
                <select 
                  value={mosfetMode} 
                  onChange={(e) => handleMosfetChange(e.target.value)}
                  style={{ background: '#111', color: 'white', border: '1px solid #555', borderRadius: '4px', padding: '4px', fontSize: '0.8rem' }}
                >
                  <option value="AUTO">🤖 Auto (50%)</option>
                  <option value="FULL">⚡ Full (100%)</option>
                </select>
              </div>

              <button className="btn-primary" style={{ padding: '8px 24px', background: '#222', border: '1px solid #444', color: 'white' }} onClick={() => setScreen('details')}>
                <Activity size={18} style={{ marginRight: '8px', verticalAlign: 'middle' }} />
                View Advanced Details
              </button>
              <button className="btn-primary" style={{ padding: '8px 24px', width: 'auto' }} onClick={() => setIsLiveViewOpen(true)}>
                <Camera size={18} style={{ marginRight: '8px', verticalAlign: 'middle' }} /> Watch Live
              </button>
            </div>
          </header>

          <main className="dashboard-grid">
            <div className="glass-panel summary-counts" style={{ gridColumn: '1 / -1' }}>
              <div style={{ padding: '20px', textAlign: 'center', borderRight: '1px solid #333' }}>
                  <AlertTriangle color="#ff2a6d" size={48} style={{ marginBottom: '10px' }} />
                  <h3 style={{ margin: 0, fontSize: '3rem', color: '#ff2a6d' }}>{criticalEvents.length}</h3>
                  <p style={{ color: '#ccc', letterSpacing: '2px', fontSize: '0.8rem' }}>🚨 CRITICAL (X/ACCIDENT)</p>
              </div>
              <div style={{ padding: '20px', textAlign: 'center', borderRight: '1px solid #333' }}>
                  <AlertTriangle color="#f39c12" size={48} style={{ marginBottom: '10px' }} />
                  <h3 style={{ margin: 0, fontSize: '3rem', color: '#f39c12' }}>{emergencyEvents.length}</h3>
                  <p style={{ color: '#ccc', letterSpacing: '2px', fontSize: '0.8rem' }}>HIGH RISK ALERTS</p>
              </div>
              <div style={{ padding: '20px', textAlign: 'center' }}>
                  <AlertCircle color="#3498db" size={48} style={{ marginBottom: '10px' }} />
                  <h3 style={{ margin: 0, fontSize: '3rem', color: '#3498db' }}>{riskEvents.length}</h3>
                  <p style={{ color: '#ccc', letterSpacing: '2px', fontSize: '0.8rem' }}>RISK / MONITORING</p>
              </div>
            </div>

            <div className="glass-panel" style={{ gridColumn: '1 / -1' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <h3>Rolling Video Buffer (Last 150 Events)</h3>
                <button className="btn-primary" style={{ width: 'auto', padding: '6px 16px', background: '#333' }} onClick={fetchEvents}>
                  🔄 Refresh Feed
                </button>
              </div>
              <div className="video-grid" style={{ maxHeight: '600px', overflowY: 'auto' }}>
              {events.map((ev) => {
                const style = getEventStyle(ev);
                const mediaUrl = ev.video_path ? `http://localhost:5000/storage/${ev.video_path}` : null;
                const isImage = mediaUrl && (mediaUrl.endsWith('.jpg') || mediaUrl.endsWith('.jpeg') || mediaUrl.endsWith('.png'));
                const isVideo = mediaUrl && (mediaUrl.endsWith('.mp4') || mediaUrl.endsWith('.avi') || mediaUrl.endsWith('.webm'));
                // Confidence: multiply by 100 only if it's a 0-1 float, not already a percentage
                const confPct = ev.confidence > 1 ? ev.confidence.toFixed(0) : (ev.confidence * 100).toFixed(0);
                return (
                  <div key={ev.id} className="video-card" style={{ border: style.border, background: style.bg }}>
                    {isVideo ? (
                        <video
                          key={ev.id}
                          src={mediaUrl}
                          controls
                          preload="metadata"
                          playsInline
                          style={{ width: '100%', height: '200px', objectFit: 'cover' }}
                        >
                          <source src={mediaUrl} type="video/mp4" />
                          Your browser does not support the video tag.
                        </video>
                    ) : isImage ? (
                        <img
                          src={mediaUrl}
                          alt={ev.event_type}
                          style={{ width: '100%', height: '200px', objectFit: 'cover', display: 'block' }}
                        />
                    ) : (
                        <div style={{ width: '100%', height: '130px', background: 'linear-gradient(45deg, #111, #222)', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                            <span style={{ color: '#555', fontSize: '0.8rem' }}>NO VIDEO FOR LOW RISK</span>
                        </div>
                    )}
                    <div className="video-info" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'end' }}>
                        <div>
                            <h4 style={{ color: style.color, margin: '4px 0' }}>{ev.event_type} — {ev.emotion}</h4>
                            <p style={{ fontSize: '0.8rem', color: '#ccc', margin: '2px 0' }}>Confidence: {confPct}% • {new Date(ev.created_at).toLocaleString()}</p>
                            {ev.activity && ev.activity !== 'UNKNOWN' && (
                              <p style={{ fontSize: '0.75rem', color: style.color, margin: '2px 0' }}>🏃 Activity: {ev.activity}</p>
                            )}
                            {ev.gesture_detected && ev.gesture_detected !== 'NONE' && (
                              <p style={{ fontSize: '0.75rem', color: '#ff2a6d', margin: '2px 0', fontWeight: 'bold' }}>✋ Gesture: {ev.gesture_detected}</p>
                            )}
                            {ev.threat_tags && ev.threat_tags.length > 0 && (
                              <p style={{ fontSize: '0.7rem', color: '#777', margin: '2px 0' }}>🏷️ {ev.threat_tags}</p>
                            )}
                        </div>
                        {(ev.risk_level === 'High' || ev.risk_level === 'Critical' || ev.event_type === 'X_GESTURE_EMERGENCY' || ev.event_type === 'ACCIDENT_DETECTED') && (
                            <button className="btn-primary" style={{ padding: '4px 12px', fontSize: '0.8rem', backgroundColor: ev.event_type === 'X_GESTURE_EMERGENCY' || ev.event_type === 'ACCIDENT_DETECTED' ? '#ff2a6d' : '#f39c12' }} onClick={() => setActionAlert(ev)}>
                                TAKE ACTION!
                            </button>
                        )}
                    </div>
                  </div>
                );
              })}
                {events.length === 0 && <p style={{ color: '#666', textAlign: 'center', width: '100%' }}>No events in the database yet.</p>}
              </div>
            </div>
            
            <div style={{ marginTop: 'auto', padding: '20px', textAlign: 'center' }}>
                <button 
                  style={{ background: 'transparent', border: '1px solid #333', color: '#555', padding: '8px 20px', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8rem' }}
                  onClick={() => setIsWipeModalOpen(true)}
                >
                  ⚙️ System Management (Clear Data)
                </button>
            </div>
          </main>
        </div>
      )}

      {/* --- DETAILS GRAPH PAGE --- */}
      {screen === 'details' && (
          <div className="animate-slide-up" style={{ flex: 1, padding: '40px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '40px' }}>
                  <h2 className="gradient-text">Advanced Threat Analytics</h2>
                  <button className="btn-primary" style={{ width: '150px' }} onClick={() => setScreen('dashboard')}>Back to Dash</button>
              </div>

              <div style={{ display: 'flex', gap: '30px' }}>
                  <div className="glass-panel" style={{ flex: 1, height: '400px' }}>
                      <h3 style={{ textAlign: 'center', marginBottom: '20px' }}>Alert Ratios</h3>
                      <ResponsiveContainer width="100%" height="90%">
                            <PieChart>
                                <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={120} label>
                                    {pieData.map((entry, index) => <Cell key={`cell-${index}`} fill={entry.color} />)}
                                </Pie>
                                <Tooltip />
                            </PieChart>
                      </ResponsiveContainer>
                  </div>
                  <div className="glass-panel" style={{ flex: 2, height: '400px' }}>
                        <h3 style={{ textAlign: 'center', marginBottom: '20px' }}>Alerts Over Time</h3>
                        <ResponsiveContainer width="100%" height="90%">
                            <LineChart data={getLineData()}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                                <XAxis dataKey="time" stroke="#aaa" />
                                <YAxis stroke="#aaa" />
                                <Tooltip contentStyle={{ backgroundColor: '#111', border: '1px solid #444' }} />
                                <Line type="monotone" dataKey="alerts" stroke="#05d5ff" strokeWidth={3} />
                            </LineChart>
                        </ResponsiveContainer>
                  </div>
              </div>
          </div>
      )}

      {/* --- LIVE VIEW MODAL --- */}
      {isLiveViewOpen && (
        <div className="modal-overlay" style={{ flexDirection: 'column', zIndex: 999 }}>
            <div style={{ width: '90%', maxWidth: '1000px', display: 'flex', justifyContent: 'space-between', marginBottom: '16px' }}>
            <h2 className="gradient-text">Live Intelligence Feed</h2>
            <button className="btn-primary" style={{ width: 'auto', padding: '8px 24px', background: 'transparent', border: '1px solid var(--neon-magenta)' }} onClick={() => setIsLiveViewOpen(false)}>
                Close
            </button>
            </div>
            <div className="glass-panel" style={{ width: '90%', maxWidth: '1000px', height: '65vh', padding: 0, overflow: 'hidden' }}>
            <img 
                src={`http://${deviceIp}:8080/stream.mjpg`} 
                alt="Live Camera Feed"
                style={{ width: '100%', height: '100%', objectFit: 'contain', background: '#000' }}
                onError={(e) => { e.target.style.display = 'none'; e.target.nextSibling.style.display = 'flex'; }}
            />
            <div style={{ display: 'none', width: '100%', height: '100%', justifyContent: 'center', alignItems: 'center', color: 'var(--neon-magenta)' }}>
                Fatal Error connecting to Edge Stream at {deviceIp}:8080
            </div>
            </div>
        </div>
      )}

      {/* --- FULL SCREEN TAKE ACTION APP MODAL --- */}
      {actionAlert && (
          <div className="modal-overlay action-modal-bg animate-slide-up">
              <div className="glass-panel" style={{ background: 'rgba(255, 42, 109, 0.1)', border: '2px solid #ff2a6d', width: '80%', maxWidth: '800px', padding: '40px', textAlign: 'center' }}>
                  <AlertTriangle size={80} color="#ff2a6d" style={{ marginBottom: '20px' }} />
                  <h1 style={{ fontSize: '3rem', color: '#ff2a6d', marginBottom: '10px' }}>EMERGENCY THREAT FILED</h1>
                  <h3 style={{ color: 'white', marginBottom: '10px' }}>TOWER: {actionAlert.tower_id} | Location: {actionAlert.location}</h3>
                  {actionAlert.activity && <p style={{ color: '#f39c12', marginBottom: '8px' }}>Activity: {actionAlert.activity} | Gesture: {actionAlert.gesture_detected}</p>}
                  {actionAlert.threat_tags && <p style={{ color: '#aaa', fontSize: '0.9rem', marginBottom: '20px' }}>Flags: {actionAlert.threat_tags}</p>}
                  
                  <div style={{ display: 'flex', gap: '20px', justifyContent: 'center' }}>
                      <a href="tel:8825750992" className="btn-primary" style={{ fontSize: '1.5rem', padding: '20px 40px', background: '#ff2a6d', display: 'flex', alignItems: 'center', gap: '15px' }}>
                          <Phone size={30} /> CALL POLICE (8825750992)
                      </a>
                      
                      <a href={`mailto:km3974808@gmail.com?subject=EMERGENCY AT TOWER ${actionAlert.tower_id}&body=Alert: ${actionAlert.event_type}%0AActivity: ${actionAlert.activity}%0ALocation: ${actionAlert.location}%0ATime: ${actionAlert.created_at}`} 
                         className="btn-primary" 
                         style={{ fontSize: '1.5rem', padding: '20px 40px', background: '#f39c12', display: 'flex', alignItems: 'center', gap: '15px' }}>
                          <Mail size={30} /> DISPATCH EMAIL
                      </a>
                  </div>
                  
                  <button className="btn-primary" style={{ marginTop: '50px', background: 'transparent', border: '1px solid #666', width: '200px' }} onClick={() => setActionAlert(null)}>
                      Dismiss Alert
                  </button>
              </div>
          </div>
      )}

      {/* --- CRITICAL EMERGENCY FLASH OVERLAY (X_GESTURE + ACCIDENT) --- */}
      {emergencyAlert && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, zIndex: 9999,
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          animation: 'emergencyFlash 0.6s infinite',
        }}>
          <style>{`
            @keyframes emergencyFlash {
              0%   { background: rgba(255,0,0,0.35); }
              50%  { background: rgba(0,100,255,0.35); }
              100% { background: rgba(255,0,0,0.35); }
            }
            @keyframes pulseScale {
              0%,100% { transform: scale(1); }
              50% { transform: scale(1.06); }
            }
          `}</style>

          <div style={{
            background: 'rgba(0,0,0,0.9)', border: '3px solid #ff2a6d',
            borderRadius: '16px', padding: '50px 60px', textAlign: 'center',
            maxWidth: '700px', width: '90%',
            animation: 'pulseScale 0.8s infinite',
          }}>
            <div style={{ fontSize: '4rem', marginBottom: '10px' }}>
              {emergencyAlert.event_type === 'X_GESTURE_EMERGENCY' ? '🆘' : '🚨'}
            </div>
            <h1 style={{ color: '#ff2a6d', fontSize: '2.5rem', margin: '0 0 10px' }}>
              {emergencyAlert.event_type === 'X_GESTURE_EMERGENCY' ? 'SOS GESTURE DETECTED!' : 'ACCIDENT DETECTED!'}
            </h1>
            <h2 style={{ color: 'white', margin: '0 0 8px' }}>Tower: {emergencyAlert.tower_id}</h2>
            <p style={{ color: '#aaa', marginBottom: '30px' }}>Location: {emergencyAlert.location} • {new Date(emergencyAlert.created_at).toLocaleTimeString()}</p>

            <div style={{ display: 'flex', gap: '16px', justifyContent: 'center', flexWrap: 'wrap' }}>
              <a href="tel:8825750992"
                style={{ background: '#ff2a6d', color: 'white', padding: '16px 32px', borderRadius: '8px', fontWeight: 'bold', fontSize: '1.2rem', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Phone size={24} /> CALL POLICE NOW
              </a>
              <a href={`mailto:km3974808@gmail.com?subject=EMERGENCY: ${emergencyAlert.event_type} at ${emergencyAlert.tower_id}&body=Gesture: ${emergencyAlert.gesture_detected}%0AActivity: ${emergencyAlert.activity}%0ALocation: ${emergencyAlert.location}%0ATime: ${emergencyAlert.created_at}`}
                style={{ background: '#0080ff', color: 'white', padding: '16px 32px', borderRadius: '8px', fontWeight: 'bold', fontSize: '1.2rem', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Mail size={24} /> EMAIL DISPATCH
              </a>
            </div>

            <button
              onClick={() => setEmergencyAlert(null)}
              style={{ marginTop: '30px', background: 'transparent', border: '1px solid #555', color: '#aaa', padding: '10px 24px', borderRadius: '6px', cursor: 'pointer', fontSize: '0.9rem' }}
            >
              Acknowledge & Dismiss
            </button>
          </div>
        </div>
      )}

      {/* --- WIPE MODAL --- */}
      {isWipeModalOpen && (
        <div className="modal-overlay" style={{ zIndex: 1000 }}>
          <div className="glass-panel animate-slide-up" style={{ width: '400px', textAlign: 'center', border: '2px solid #ff2a6d' }}>
            <h2 style={{ color: '#ff2a6d', marginBottom: '8px' }}>Global Data Wipe</h2>
            <p style={{ color: 'var(--text-muted)', marginBottom: '24px', fontSize: '0.9rem' }}>
                Enter management credentials to permanently delete all alerts and history.
            </p>
            
            <form onSubmit={handleWipe}>
              <div style={{ marginBottom: '16px' }}>
                <input 
                  type="text" 
                  className="input-field" 
                  placeholder="Management ID" 
                  value={wipeUser}
                  onChange={e => setWipeUser(e.target.value)}
                  required
                />
              </div>
              <div style={{ marginBottom: '24px' }}>
                <input 
                  type="password" 
                  className="input-field" 
                  placeholder="Management Pass" 
                  value={wipePass}
                  onChange={e => setWipePass(e.target.value)}
                  required
                />
              </div>
              <div style={{ display: 'flex', gap: '12px' }}>
                <button type="button" className="btn-primary" style={{ background: '#222', border: '1px solid #444' }} onClick={() => setIsWipeModalOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn-primary" style={{ background: '#ff2a6d' }}>
                  Confirm Wipe
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default App;
