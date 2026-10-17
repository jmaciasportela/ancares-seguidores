/**
 * Marcador en directo.
 *
 * - Quien anota (el anotador principal) emite el estado completo del marcador en
 *   cada cambio: un reintento nunca descuadra nada y el servidor ignora lo atrasado
 *   gracias a `seq`. Cada minuto manda un latido para que se sepa que sigue ahí.
 * - Las familias lo reciben por WebSocket. Si no conecta (proxy sin WebSockets,
 *   redes raras), consultan cada 5 s y siguen probando el WebSocket de vez en cuando.
 */
import { api } from './api.js';
import { isOursName } from './format.js';
import * as S from './scoring.js';

const EMPTY_SET = [0, 0, false];

/** ¿Hay que darle la vuelta al marcador para que cuadre con local/visitante del partido de liga? */
export function flipFor(game) {
  if (!game?.match || !game.oursSide) return false;
  return game.oursSide !== (isOursName(game.match.home) ? 'home' : 'away');
}

/** Estado compacto que se emite, siempre en local/visitante del partido de liga. */
export function toLive(game) {
  const flip = flipFor(game);
  return {
    format: game.format,
    sets: game.sets.map((s) => (flip ? [s.away, s.home, s.done] : [s.home, s.away, s.done])),
    serve: game.serve ? (flip ? S.other(game.serve) : game.serve) : null,
    status: game.status,
    finished_early: !!game.finishedEarly,
  };
}

/** Reconstruye un partido de scoring.js a partir del estado emitido (para reutilizar su lógica). */
export function fromLive(state, { home = { name: 'Local' }, away = { name: 'Visitante' }, oursSide = null, match = null } = {}) {
  const now = Date.now();
  return {
    v: 1,
    format: { ...state.format },
    home: { ...home },
    away: { ...away },
    match,
    oursSide,
    sets: (state.sets?.length ? state.sets : [EMPTY_SET]).map(([h, a, done]) => ({ home: h, away: a, done: !!done })),
    serve: state.serve ?? null,
    status: state.status || 'playing',
    finishedEarly: !!state.finished_early,
    swapped: false,
    history: [],
    startedAt: now,
    updatedAt: now,
  };
}

/** ¿Lleva algún punto? (para decidir si se sigue desde lo emitido o se empieza de cero) */
export const hasProgress = (state) => !!state?.sets?.some(([h, a]) => h || a) && state.status !== 'finished';

/** Marcador corto: «Set 2: 18-15 · sets 1-0», o «2-1» si ha terminado. */
export function liveScoreText(state) {
  const g = fromLive(state);
  const won = S.setsWon(g);
  const cur = S.currentSet(g);
  if (state.status === 'finished' || state.status === 'match_over') return `${won.home}-${won.away}`;
  return `Set ${g.sets.length}: ${cur.home}-${cur.away}${won.home || won.away ? ` · sets ${won.home}-${won.away}` : ''}`;
}

/**
 * Qué ha pasado entre dos estados, para animarlo en el visor.
 * Devuelve una lista de {type: 'point'|'undo'|'set'|'newset'|'court'|'end', side?}.
 */
export function liveEvents(prev, next) {
  if (!prev || !next) return [];
  const a = fromLive(prev);
  const b = fromLive(next);
  const events = [];
  const pa = S.currentSet(a);
  const pb = S.currentSet(b);
  if (b.sets.length > a.sets.length) {
    // Si el set anterior se cerró en este mismo cambio, también es fin de set
    const closed = b.sets[a.sets.length - 1];
    if (closed && closed.done && !pa.done) events.push({ type: 'set', side: closed.home > closed.away ? 'home' : 'away' });
    events.push({ type: 'newset', no: b.sets.length });
  } else if (b.sets.length === a.sets.length) {
    const dh = pb.home - pa.home;
    const da = pb.away - pa.away;
    if (dh > 0 && da === 0) events.push({ type: 'point', side: 'home' });
    else if (da > 0 && dh === 0) events.push({ type: 'point', side: 'away' });
    else if (dh < 0 || da < 0) events.push({ type: 'undo' });
    if (pb.done && !pa.done) events.push({ type: 'set', side: pb.home > pb.away ? 'home' : 'away' });
    if (S.isCourtChange(a, b)) events.push({ type: 'court' });
  }
  const over = (g) => g.status === 'match_over' || g.status === 'finished';
  if (over(b) && !over(a)) events.push({ type: 'end', side: S.matchWinner(b) });
  return events;
}

// --- anotador ----------------------------------------------------------------------

export const claimLive = (liveId, takeover = false) =>
  api(`/api/live/${liveId}/claim`, { method: 'POST', json: { takeover } });

/**
 * Emisor del anotador principal. `onInfo` recibe {status, viewers, by, message}:
 * status = 'connecting' | 'ok' | 'retrying' | 'lost' (otro tomó el relevo) | 'revoked' | 'stopped'.
 */
export function createEmitter(liveId, onInfo = () => {}) {
  let seq = 0;
  let ready = false;
  let latest = null;
  let lastJson = '';
  let timer = null;
  let retry = 0;
  let inflight = false;
  let dead = false;
  let info = { status: 'connecting', viewers: 0, by: null, message: '' };
  const set = (patch) => onInfo((info = { ...info, ...patch }));

  function fail(err) {
    if (err.status === 409 || err.status === 401) {
      dead = true;
      clearTimeout(timer);
      clearInterval(beat);
      set({ status: err.status === 401 ? 'revoked' : 'lost', by: err.data?.by || null, message: err.message });
      return true;
    }
    return false;
  }

  // Al conectarse (o volver a la pantalla) se confirma que sigue siendo el principal
  claimLive(liveId)
    .then((r) => {
      seq = r.seq;
      ready = true;
      set({ status: 'ok', viewers: r.viewers });
      if (latest) schedule(0);
    })
    .catch((err) => {
      if (!fail(err)) {
        ready = true; // sin conexión: se reintentará al enviar
        set({ status: 'retrying', message: err.message });
        if (latest) schedule(2000);
      }
    });

  function schedule(ms) {
    clearTimeout(timer);
    timer = setTimeout(flush, ms);
  }

  async function flush() {
    if (dead || !ready || !latest) return;
    if (inflight) return schedule(300);
    inflight = true;
    try {
      const r = await api(`/api/live/${liveId}`, { method: 'POST', json: { seq, state: latest } });
      retry = 0;
      set({ status: 'ok', viewers: r.viewers, message: '' });
    } catch (err) {
      if (!fail(err)) {
        retry += 1;
        set({ status: 'retrying', message: err.message });
        schedule(Math.min(2000 * 2 ** (retry - 1), 20000));
      }
    } finally {
      inflight = false;
    }
  }

  // Latido: aunque no haya puntos (tiempo muerto, entre sets) se sabe que el anotador sigue ahí
  const beat = setInterval(() => !inflight && latest && flush(), 60000);

  return {
    /** Emite el estado del marcador (agrupando toques muy seguidos). */
    send(state) {
      if (dead) return;
      const json = JSON.stringify(state);
      if (json === lastJson) return;
      lastJson = json;
      latest = state;
      seq += 1;
      schedule(250);
    },
    /** Deja de emitir y libera el puesto de anotador principal. */
    async stop() {
      const wasDead = dead;
      this.dispose();
      set({ status: 'stopped' });
      if (!wasDead) await api(`/api/live/${liveId}`, { method: 'DELETE' }).catch(() => {});
    },
    /** Sale de la pantalla sin liberar el puesto (el partido sigue guardado en el móvil). */
    dispose() {
      dead = true;
      clearTimeout(timer);
      clearInterval(beat);
    },
  };
}

// --- visor -----------------------------------------------------------------------

/**
 * Conecta un visor. `onMessage` recibe los mensajes del servidor
 * ({type: 'state'|'waiting'|'viewers'|'ping', ...}) y `onStatus` el estado de la
 * conexión: 'connecting' | 'live' | 'reconnecting' | 'polling' | 'gone'.
 */
export function connectLive(liveId, onMessage, onStatus = () => {}) {
  let ws = null;
  let closed = false;
  let failures = 0;
  let retryTimer = null;
  let pollTimer = null;
  let watchdog = null;
  let lastSeq = -1;

  function deliver(msg) {
    if (msg.type === 'state') {
      if (msg.seq < lastSeq) return; // algo atrasado (p. ej. una consulta que llega tarde)
      lastSeq = msg.seq;
    }
    onMessage(msg);
  }

  // El servidor manda un ping cada 25 s: si pasa un minuto sin noticias, la conexión está muerta
  function kick() {
    clearTimeout(watchdog);
    watchdog = setTimeout(() => ws?.close(), 60000);
  }

  function open() {
    if (closed || ws) return;
    clearTimeout(retryTimer);
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    try {
      ws = new WebSocket(`${proto}://${location.host}/api/live/${liveId}/ws`);
    } catch {
      ws = null;
      return fail();
    }
    ws.onmessage = (e) => {
      kick();
      let msg;
      try {
        msg = JSON.parse(e.data);
      } catch {
        return;
      }
      if (failures) failures = 0;
      stopPolling();
      onStatus('live');
      deliver(msg);
    };
    ws.onclose = (e) => {
      clearTimeout(watchdog);
      ws = null;
      if (closed) return;
      if (e.code === 4404) return onStatus('gone');
      failures += e.code === 4429 ? 3 : 1; // demasiados visores: directamente a consultas
      fail();
    };
  }

  function fail() {
    if (closed) return;
    if (failures >= 3) {
      startPolling();
      retryTimer = setTimeout(open, 60000);
    } else {
      onStatus('reconnecting');
      retryTimer = setTimeout(open, Math.min(1000 * 2 ** (failures - 1), 8000));
    }
  }

  async function poll() {
    try {
      const r = await api(`/api/live/${liveId}`);
      deliver(r.live || { type: 'waiting', viewers: r.viewers });
    } catch (err) {
      if (err.status === 404) {
        stopPolling();
        onStatus('gone');
      }
    }
  }

  function startPolling() {
    if (pollTimer) return;
    onStatus('polling');
    poll();
    pollTimer = setInterval(poll, 5000);
  }

  function stopPolling() {
    clearInterval(pollTimer);
    pollTimer = null;
  }

  // Al volver a la app (el móvil corta los sockets en segundo plano), reconectar ya
  function onVisible() {
    if (document.visibilityState !== 'visible' || closed) return;
    if (pollTimer) poll();
    if (!ws) {
      failures = Math.min(failures, 2);
      open();
    }
  }
  document.addEventListener('visibilitychange', onVisible);

  onStatus('connecting');
  open();

  return {
    close() {
      closed = true;
      clearTimeout(retryTimer);
      clearTimeout(watchdog);
      stopPolling();
      document.removeEventListener('visibilitychange', onVisible);
      ws?.close();
    },
  };
}
