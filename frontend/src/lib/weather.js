import { api } from './api.js';

/** Código meteorológico WMO (Open-Meteo) -> icono y texto. */
const CODES = [
  [[0], '☀️', '🌙', 'Despejado'],
  [[1], '🌤️', '🌙', 'Poco nuboso'],
  [[2], '⛅', '☁️', 'Intervalos nubosos'],
  [[3], '☁️', '☁️', 'Nublado'],
  [[45, 48], '🌫️', '🌫️', 'Niebla'],
  [[51, 53, 55], '🌦️', '🌧️', 'Llovizna'],
  [[56, 57, 66, 67], '🌧️', '🌧️', 'Lluvia helada'],
  [[61, 63], '🌧️', '🌧️', 'Lluvia'],
  [[65], '🌧️', '🌧️', 'Lluvia fuerte'],
  [[71, 73, 75, 77], '❄️', '❄️', 'Nieve'],
  [[80, 81, 82], '🌦️', '🌧️', 'Chubascos'],
  [[85, 86], '🌨️', '🌨️', 'Chubascos de nieve'],
  [[95], '⛈️', '⛈️', 'Tormenta'],
  [[96, 99], '⛈️', '⛈️', 'Tormenta con granizo'],
];

export function describeWeather(code, isDay = true) {
  const row = CODES.find(([codes]) => codes.includes(code));
  if (!row) return { icon: '🌡️', label: 'Previsión' };
  return { icon: isDay ? row[1] : row[2], label: row[3] };
}

// Caché en memoria: la previsión cambia poco y el servidor ya cachea 30 min
const cache = new Map();

export function weatherFor(match) {
  const key = `${match.id}|${match.starts_at}`;
  if (!cache.has(key)) {
    cache.set(
      key,
      api(`/api/weather/${match.id}`).catch((err) => {
        cache.delete(key); // reintentar la próxima vez
        throw err;
      }),
    );
  }
  return cache.get(key);
}
