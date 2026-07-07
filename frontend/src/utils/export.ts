import type { Aircraft, Anomaly } from '@/types';

export function exportToCSV(aircraft: Aircraft[], filename: string = 'aircraft_data'): void {
  const headers = [
    'ICAO',
    'Callsign',
    'Latitude',
    'Longitude',
    'Altitude (ft)',
    'Ground Speed (kts)',
    'Track (deg)',
    'Vertical Rate (fpm)',
    'Squawk',
    'Last Seen',
    'First Seen',
    'Messages',
  ];

  const rows = aircraft.map(a => [
    a.icao_hex,
    a.callsign || '',
    a.latitude?.toFixed(6) || '',
    a.longitude?.toFixed(6) || '',
    a.altitude?.toString() || '',
    a.ground_speed?.toFixed(0) || '',
    a.track?.toFixed(0) || '',
    a.vertical_rate?.toString() || '',
    a.squawk || '',
    a.last_seen,
    a.first_seen,
    a.messages_received.toString(),
  ]);

  const csvContent = [
    headers.join(','),
    ...rows.map(row => row.map(cell => `"${cell}"`).join(',')),
  ].join('\n');

  downloadFile(csvContent, `${filename}_${getTimestamp()}.csv`, 'text/csv');
}

export function exportToJSON(aircraft: Aircraft[], filename: string = 'aircraft_data'): void {
  const exportData = {
    exported_at: new Date().toISOString(),
    aircraft_count: aircraft.length,
    aircraft: aircraft.map(a => ({
      icao_hex: a.icao_hex,
      callsign: a.callsign,
      position: a.latitude && a.longitude ? {
        latitude: a.latitude,
        longitude: a.longitude,
      } : null,
      altitude_ft: a.altitude,
      ground_speed_kts: a.ground_speed,
      track_deg: a.track,
      vertical_rate_fpm: a.vertical_rate,
      squawk: a.squawk,
      last_seen: a.last_seen,
      first_seen: a.first_seen,
      messages_received: a.messages_received,
    })),
  };

  const jsonContent = JSON.stringify(exportData, null, 2);
  downloadFile(jsonContent, `${filename}_${getTimestamp()}.json`, 'application/json');
}

export function exportAnomaliesToCSV(anomalies: Anomaly[], filename: string = 'anomalies'): void {
  const headers = [
    'ID',
    'ICAO',
    'Callsign',
    'Type',
    'Severity',
    'Latitude',
    'Longitude',
    'Altitude',
    'Description',
    'Detected At',
    'Resolved At',
    'Acknowledged',
  ];

  const rows = anomalies.map(a => [
    a.id.toString(),
    a.icao_hex,
    a.callsign || '',
    a.anomaly_type,
    a.severity,
    a.latitude?.toFixed(6) || '',
    a.longitude?.toFixed(6) || '',
    a.altitude?.toString() || '',
    a.description || '',
    a.detected_at,
    a.resolved_at || '',
    a.acknowledged.toString(),
  ]);

  const csvContent = [
    headers.join(','),
    ...rows.map(row => row.map(cell => `"${cell.replace(/"/g, '""')}"`).join(',')),
  ].join('\n');

  downloadFile(csvContent, `${filename}_${getTimestamp()}.csv`, 'text/csv');
}

function getTimestamp(): string {
  const now = new Date();
  return now.toISOString().replace(/[:.]/g, '-').slice(0, 19);
}

function downloadFile(content: string, filename: string, mimeType: string): void {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
