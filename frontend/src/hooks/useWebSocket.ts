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

export function useWebSocket(): UseWebSocketReturn {
  const [aircraft, setAircraft] = useState<Aircraft[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [connected, setConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectDelayRef = useRef(1000); // Start at 1 second

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.hostname}:8000/api/v1/ws/aircraft`;

    try {
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        setConnected(true);
        reconnectDelayRef.current = 1000; // Reset delay on successful connection
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
        // Exponential backoff: 1s, 2s, 4s, 8s, max 30s
        const delay = Math.min(reconnectDelayRef.current, 30000);
        console.log(`WebSocket disconnected, reconnecting in ${delay / 1000}s...`);
        reconnectTimeoutRef.current = setTimeout(connect, delay);
        reconnectDelayRef.current = Math.min(reconnectDelayRef.current * 2, 30000);
      };

      ws.onerror = () => {
        // Don't log error spam, just close and let onclose handle reconnect
        ws.close();
      };

      wsRef.current = ws;
    } catch {
      // Connection failed, schedule retry
      const delay = Math.min(reconnectDelayRef.current, 30000);
      reconnectTimeoutRef.current = setTimeout(connect, delay);
      reconnectDelayRef.current = Math.min(reconnectDelayRef.current * 2, 30000);
    }
  }, []);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  return { aircraft, stats, connected, lastUpdate };
}
