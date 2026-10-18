<script>
  import { onMount } from 'svelte';
  import CheerBar from '../components/CheerBar.svelte';
  import Icon from '../components/Icon.svelte';
  import ScorePad from '../components/ScorePad.svelte';
  import TeamBadge from '../components/TeamBadge.svelte';
  import { api, resource } from '../lib/api.js';
  import { formatWhen, isOursName, scoreOf, shortTeam } from '../lib/format.js';
  import { connectLive, fromLive, liveEvents, liveScoreText } from '../lib/live.js';
  import { fade, pop } from '../lib/motion.js';
  import { back, go } from '../lib/router.js';
  import * as S from '../lib/scoring.js';
  import { shareText } from '../lib/share.js';
  import { keepScreenOn } from '../lib/wakelock.js';

  /** Visor del marcador en directo: lo que emite el anotador principal, al momento. */
  let { id } = $props();

  let match = $state(null);
  let missing = $state(false);
  let live = $state.raw(null); // último estado recibido: {state, on, seq, lead_age}
  let ready = $state(false); // el anotador ya está dentro, aunque aún no haya tanteo
  let viewers = $state(0);
  let conn = $state('connecting'); // connecting | live | reconnecting | polling | gone
  let leadAge = $state(null);
  let leadAt = $state(0);
  let now = $state(Date.now());
  let flash = $state({ home: 0, away: 0 });
  let banner = $state(null); // {text, big}
  let bannerTimer;

  const oursSide = $derived(match && isOursName(match.away) && !isOursName(match.home) ? 'away' : 'home');
  const team = (side) => ({ name: match[side], logo: match[`${side}_logo`] });
  const game = $derived(live?.state && match ? fromLive(live.state, { home: team('home'), away: team('away'), oursSide }) : null);
  const won = $derived(game ? S.setsWon(game) : { home: 0, away: 0 });
  const over = $derived(game && (game.status === 'match_over' || game.status === 'finished'));
  // Ancares abajo, como en el marcador
  const order = $derived(oursSide === 'home' ? ['away', 'home'] : ['home', 'away']);
  const hint = (side) =>
    game.status !== 'playing' ? '' : S.isMatchPoint(game, side) ? 'Punto de partido' : S.isSetPoint(game, side) ? 'Punto de set' : '';
  const done = $derived(game ? game.sets.filter((s, i) => s.done && (i < game.sets.length - 1 || over)) : []);
  // Marcador preparado a 0-0: el partido aún no ha empezado
  const notStarted = $derived(
    !!game && game.status === 'playing' && game.sets.length === 1 && !S.currentSet(game).home && !S.currentSet(game).away,
  );
  // Segundos sin señal del anotador (el servidor lo dice al conectar y en cada ping)
  const silent = $derived(leadAge == null ? 0 : leadAge + (now - leadAt) / 1000);

  const status = $derived.by(() => {
    if (conn === 'gone') return { text: 'No disponible', tone: 'off' };
    if (!live) return conn === 'reconnecting' ? { text: 'Reconectando…', tone: 'wait' } : ready ? { text: 'Lista', tone: 'ready' } : { text: 'Esperando', tone: 'wait' };
    if (over) return { text: 'Final', tone: 'end' };
    if (!live.on) return { text: 'Retransmisión parada', tone: 'off' };
    if (notStarted && silent <= 180) return { text: 'Lista', tone: 'ready' };
    if (silent > 180) return { text: `Sin señal hace ${Math.round(silent / 60)} min`, tone: 'off' };
    if (conn === 'reconnecting') return { text: 'Reconectando…', tone: 'wait' };
    return { text: 'En directo', tone: 'live' };
  });

  function showBanner(text, big = false, ms = 3500) {
    clearTimeout(bannerTimer);
    banner = { text, big, key: Date.now() };
    if (ms) bannerTimer = setTimeout(() => (banner = null), ms);
  }

  function onMessage(msg) {
    if (msg.viewers != null) viewers = msg.viewers;
    if (msg.lead_age != null) {
      leadAge = msg.lead_age;
      leadAt = Date.now();
    }
    if (msg.type === 'ready') ready = true;
    if (msg.type === 'waiting') ready = false;
    if (msg.type !== 'state') return;
    const prev = live?.state;
    live = msg;
    if (!match) return;
    for (const e of liveEvents(prev, msg.state)) {
      const g = fromLive(msg.state);
      if (e.type === 'point') flash = { ...flash, [e.side]: flash[e.side] + 1 };
      else if (e.type === 'set') {
        const s = g.sets.filter((x) => x.done).at(-1);
        showBanner(`Set para ${shortTeam(match[e.side])} · ${s.home}-${s.away}`);
      } else if (e.type === 'court') showBanner('Cambio de campo');
      else if (e.type === 'end') {
        const ours = e.side === oursSide;
        showBanner(e.side === 'draw' ? '¡Empate!' : ours ? '¡VICTORIA!' : `Gana ${shortTeam(match[e.side])}`, true, 6000);
        navigator.vibrate?.(ours ? [60, 40, 60] : 30);
      }
    }
  }

  onMount(() => {
    let connection = null;
    let cancelled = false;
    api(`/api/live/${id}`)
      .then((r) => {
        if (cancelled) return;
        match = r.match;
        viewers = r.viewers;
        if (r.live) onMessage(r.live);
        else ready = !!r.ready;
        connection = connectLive(id, onMessage, (s) => (conn = s));
      })
      .catch((err) => {
        if (err.status === 404) missing = true;
        else connection = connectLive(id, onMessage, (s) => (conn = s)); // sin red: el visor reintenta
      });
    const tick = setInterval(() => (now = Date.now()), 10000);
    return () => {
      cancelled = true;
      connection?.close();
      clearInterval(tick);
      clearTimeout(bannerTimer);
      resource('/api/home').refresh(); // al volver, la portada ya con el tanteo al día
    };
  });

  // Pantalla encendida mientras se sigue el partido
  $effect(() => {
    if (game && !over) return keepScreenOn();
  });

  function share() {
    const title = `🔴 En directo: ${shortTeam(match.home)} vs ${shortTeam(match.away)}`;
    const text = live?.state ? `${title}\n${liveScoreText(live.state)}\n${match.category} · ${match.round_name}` : `${title}\n${match.category} · ${match.round_name}`;
    shareText(text, `${location.origin}/#/directo/${id}`);
  }

  const result = $derived(match ? scoreOf(match) : null);
</script>

<div class="viewer">
  <header class="bar">
    <button class="icon-btn" onclick={() => back('/')} aria-label="Volver"><Icon name="back" size={22} /></button>
    <div class="status">
      <b class="state {status.tone}">{#if status.tone === 'live'}<i></i>{/if}{status.text}</b>
      <span>{match ? `${match.category} · ${match.round_name}` : 'Marcador en directo'}</span>
    </div>
    <button class="icon-btn" onclick={share} disabled={!match} aria-label="Compartir el directo"><Icon name="share" size={20} /></button>
  </header>

  {#if missing}
    <div class="empty" in:fade>
      <p>No encuentro este partido.</p>
      <button class="btn" onclick={() => go('/')}>Ir al inicio</button>
    </div>
  {:else if !match}
    <div class="empty"><div class="spinner" aria-label="Cargando"></div></div>
  {:else if game}
    <div class="pads" class:stopped={status.tone === 'off'}>
      {#each order as side (side)}
        <ScorePad
          readonly
          team={team(side)}
          points={S.currentSet(game)[side]}
          sets={won[side]}
          setsToWin={S.setsToWin(game.format)}
          serving={!over && game.serve === side}
          tone={side === oursSide ? 'green' : 'dark'}
          hint={hint(side)}
          flash={flash[side]}
        />
      {/each}
      {#if notStarted && !banner && live.on}
        <div class="banner soft" transition:fade>🏐 Todo listo: esperando el primer punto</div>
      {/if}
      {#if banner}
        {#key banner.key}
          <div class="banner" class:big={banner.big} in:pop out:fade>{banner.text}</div>
        {/key}
      {/if}
    </div>

    <footer class="foot">
      <div class="line">
        <span class="sets-done">
          {#if over}<b>Final {won.home}-{won.away}</b>{:else}<b>Set {game.sets.length}</b>{/if}
          {#each done as s, i}<span>{s.home}-{s.away}</span>{/each}
        </span>
        <span class="viewers" title="Personas viendo el directo">👀 {viewers}</span>
      </div>
      {#if match.cheers?.open}<CheerBar {match} />{/if}
    </footer>
  {:else}
    <div class="waiting" in:fade>
      <div class="vs">
        <div class="team"><TeamBadge name={match.home} logo={match.home_logo} size={64} /><b>{shortTeam(match.home)}</b></div>
        <span class="x">vs</span>
        <div class="team"><TeamBadge name={match.away} logo={match.away_logo} size={64} /><b>{shortTeam(match.away)}</b></div>
      </div>
      {#if result}
        <p class="big">{result.home} - {result.away}</p>
        <p class="muted-light">Este partido ya tiene resultado{result.provisional ? ' provisional' : ''}.</p>
        <button class="btn light" onclick={() => go(`/c/${match.category_slug}?t=resultados`)}>Ver resultados</button>
      {:else}
        <p class="when">{formatWhen(match.starts_at)}</p>
        {#if ready}
          <p class="pulse ready"><i></i> Retransmisión lista</p>
          <p class="muted-light">El marcador ya está preparado: en cuanto empiece el partido verás aquí cada punto al momento.</p>
        {:else}
          <p class="pulse"><i></i> Aún no ha empezado la retransmisión</p>
          <p class="muted-light">Esta pantalla se actualizará sola en cuanto alguien empiece a llevar el marcador.</p>
        {/if}
        {#if viewers > 1}<p class="muted-light">👀 {viewers} esperando</p>{/if}
      {/if}
      {#if match.cheers?.open}<div class="cheer-wrap"><CheerBar {match} /></div>{/if}
    </div>
  {/if}
</div>

<style>
  .viewer {
    position: fixed;
    inset: 0;
    z-index: 50;
    display: grid;
    grid-template-rows: auto 1fr auto;
    background: #0b1a10;
    color: #fff;
  }
  .bar {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: calc(var(--safe-top) + 6px) 8px 6px;
  }
  .icon-btn {
    width: 44px;
    height: 44px;
    display: grid;
    place-items: center;
    border-radius: 50%;
    color: #fff;
  }
  .icon-btn:active {
    background: rgba(255, 255, 255, 0.12);
  }
  .status {
    flex: 1;
    min-width: 0;
    display: grid;
    justify-items: center;
    text-align: center;
    gap: 2px;
    line-height: 1.2;
  }
  .status span {
    max-width: 100%;
    font-size: 13.5px;
    opacity: 0.75;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .state {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 12.5px;
    font-weight: 900;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    background: rgba(255, 255, 255, 0.1);
  }
  .state.live {
    background: #fff;
    color: #d92d33;
  }
  .state.live i {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #ff3b41;
    animation: blink 1s infinite;
  }
  .state.end,
  .state.ready {
    background: #8ee39c;
    color: #0b1a10;
  }
  .state.off {
    color: #ffcf6e;
  }
  @keyframes blink {
    50% {
      opacity: 0.25;
    }
  }

  .pads {
    position: relative;
    display: grid;
    grid-template-rows: 1fr 1fr;
    gap: 3px;
    min-height: 0;
    transition: filter 0.3s;
  }
  .pads.stopped {
    filter: grayscale(0.6) brightness(0.8);
  }
  .banner {
    position: absolute;
    left: 50%;
    top: 50%;
    translate: -50% -50%;
    z-index: 2;
    max-width: 90%;
    padding: 12px 22px;
    border-radius: 999px;
    background: #fff;
    color: #0b1a10;
    font-size: 18px;
    font-weight: 850;
    text-align: center;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
  }
  .banner.soft {
    width: max-content;
    max-width: 84%;
    white-space: normal;
    border-radius: 18px;
    background: rgba(11, 26, 16, 0.88);
    color: #fff;
    font-size: 16px;
    font-weight: 750;
    line-height: 1.3;
    border: 1px solid rgba(142, 227, 156, 0.5);
  }
  .banner.big {
    padding: 18px 30px;
    font-size: 30px;
    background: linear-gradient(120deg, #3bbf50, #1f7f30);
    color: #fff;
  }

  .foot {
    padding: 10px 14px calc(var(--safe-bottom) + 8px);
    display: grid;
    gap: 8px;
  }
  .line {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    font-variant-numeric: tabular-nums;
  }
  .sets-done {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 4px 10px;
    font-size: 14px;
    min-width: 0;
  }
  .sets-done b {
    color: #8ee39c;
    letter-spacing: 0.04em;
  }
  .sets-done span {
    opacity: 0.8;
  }
  .viewers {
    flex: none;
    font-size: 14px;
    opacity: 0.85;
  }
  .foot :global(.cheers) {
    margin-bottom: 0;
  }

  .empty,
  .waiting {
    display: grid;
    align-content: center;
    justify-items: center;
    gap: 12px;
    padding: 20px;
    text-align: center;
  }
  .vs {
    display: flex;
    align-items: center;
    gap: 18px;
  }
  .team {
    display: grid;
    justify-items: center;
    gap: 8px;
    max-width: 130px;
    font-size: 15px;
  }
  .x {
    font-weight: 800;
    opacity: 0.6;
  }
  .when {
    margin: 4px 0 0;
    font-size: 20px;
    font-weight: 800;
    color: #8ee39c;
  }
  .big {
    margin: 0;
    font-size: 48px;
    font-weight: 850;
  }
  .pulse {
    margin: 8px 0 0;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-weight: 700;
  }
  .pulse.ready {
    color: #8ee39c;
  }
  .pulse i {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: #8ee39c;
    animation: blink 1.4s infinite;
  }
  .muted-light {
    margin: 0;
    max-width: 320px;
    font-size: 14px;
    opacity: 0.7;
  }
  .cheer-wrap {
    width: 100%;
    max-width: 380px;
    margin-top: 16px;
  }
  .light {
    background: rgba(255, 255, 255, 0.14);
    color: #fff;
  }
  .spinner {
    width: 34px;
    height: 34px;
    border-radius: 50%;
    border: 3px solid rgba(255, 255, 255, 0.2);
    border-top-color: #8ee39c;
    animation: spin 0.8s linear infinite;
  }
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .state.live i,
    .pulse i,
    .spinner {
      animation: none;
    }
  }
</style>
