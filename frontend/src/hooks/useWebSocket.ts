import { useEffect, useRef, useState, useCallback } from 'react';
import type { Aircraft, Stats } from '@/types';

interface WebSocketMessage {
  type: 'update';
  aircraft: Aircraft[];
  stats: Stats;
  timestamp: string;
}

interface UseWebSocketReturn {
  aircraft: Aircraft[];
  stats: Stats | null;
  connected: boolean;
  lastUpdate: Date | null;
}

// Fallback: fetch via REST API
async function fetchAircraftREST(): Promise<{ aircraft: Aircraft[]; stats: Stats | null }> {
  try {
    const [aircraftRes, statsRes] = await Promise.all([
      fetch('/api/v1/aircraft/'),
      fetch('/api/v1/aircraft/stats/overview'),
    ]);
    const aircraft = await aircraftRes.json();
    const stats = await statsRes.json();
    return { aircraft, stats };
  } catch (e) {
    console.error('REST fetch failed:', e);
    return { aircraft: [], stats: null };
  }
}

export function useWebSocket(): UseWebSocketReturn {
  const [aircraft, setAircraft] = useState<Aircraft[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [connected, setConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectDelayRef = useRef(1000);

  // Fallback polling when WebSocket fails
  const startPolling = useCallback(() => {
    if (pollIntervalRef.current) return;
    console.log('Starting REST polling fallback...');

    // Immediate fetch
    fetchAircraftREST().then(({ aircraft, stats }) => {
      setAircraft(aircraft);
      setStats(stats);
      setLastUpdate(new Date());
    });

    // Poll every 2 seconds
    pollIntervalRef.current = setInterval(async () => {
      const { aircraft, stats } = await fetchAircraftREST();
      setAircraft(aircraft);
      setStats(stats);
      setLastUpdate(new Date());
    }, 2000);
  }, []);

  const stopPolling = useCallback(() => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/v1/ws/aircraft`;

    try {
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        setConnected(true);
        reconnectDelayRef.current = 1000;
        stopPolling(); // Stop polling when WS connects
        console.log('WebSocket connected');
      };

      ws.onmessage = (event) => {
        try {
          const data: WebSocketMessage = JSON.parse(event.data);
          if (data.type === 'update') {
            setAircraft(data.aircraft);
            setStats(data.stats);
            setLastUpdate(new Date());
          }
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e);
        }
      };

      ws.onclose = () => {
        setConnected(false);
        startPolling(); // Start polling as fallback
        const delay = Math.min(reconnectDelayRef.current, 30000);
        console.log(`WebSocket disconnected, reconnecting in ${delay / 1000}s...`);
        reconnectTimeoutRef.current = setTimeout(connect, delay);
        reconnectDelayRef.current = Math.min(reconnectDelayRef.current * 2, 30000);
      };

      ws.onerror = () => {
        ws.close();
      };

      wsRef.current = ws;
    } catch {
      startPolling(); // Start polling as fallback
      const delay = Math.min(reconnectDelayRef.current, 30000);
      reconnectTimeoutRef.current = setTimeout(connect, delay);
      reconnectDelayRef.current = Math.min(reconnectDelayRef.current * 2, 30000);
    }
  }, [startPolling, stopPolling]);

  useEffect(() => {
    // Start with REST fetch immediately, then try WebSocket
    fetchAircraftREST().then(({ aircraft, stats }) => {
      setAircraft(aircraft);
      setStats(stats);
      setLastUpdate(new Date());
    });

    connect();

    return () => {
      stopPolling();
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect, stopPolling]);

  return { aircraft, stats, connected, lastUpdate };
}
