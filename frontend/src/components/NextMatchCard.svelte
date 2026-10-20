<script>
  import Countdown from './Countdown.svelte';
  import Icon from './Icon.svelte';
  import TeamBadge from './TeamBadge.svelte';
  import CheerBar from './CheerBar.svelte';
  import WeatherChip from './WeatherChip.svelte';
  import { directionsUrl, formatDay, formatTime, isToday, liveMode, mapsUrl, roundLabel, shortTeam } from '../lib/format.js';
  import TodayBadge from './TodayBadge.svelte';
  import { pop } from '../lib/motion.js';
  import { go } from '../lib/router.js';
  import { matchText } from '../lib/share.js';
  import { openShare } from '../lib/shareSheet.js';
  import { dataFromMatch } from '../lib/shareData.js';

  let { match, category } = $props();
  // Día del partido: resaltado, «Llevar marcador» y ruta hasta el pabellón
  const today = $derived(isToday(match.starts_at));
  // Marcador en directo: si alguien lo está retransmitiendo, se ve el tanteo en la tarjeta
  const live = $derived(match.live);
  const mode = $derived(liveMode(live));
</script>

<article class="next" class:today id="match-{match.id}">
  <header>
    <span class="label">Próximo partido</span>
    {#if today || mode}<TodayBadge startsAt={match.starts_at} {live} />{:else}<span class="round" class:shift={match.round_shift}>{roundLabel(match)}</span>{/if}
  </header>

  <div class="teams">
    <div class="team">
      <TeamBadge name={match.home} logo={match.home_logo} size={52} />
      <span class="name">{shortTeam(match.home)}</span>
    </div>
    <div class="vs">
      {#if mode}
        {@const big = mode === 'final' ? live.sets : live.current}
        {#key big.join()}<span class="time score" in:pop>{big[0]}-{big[1]}</span>{/key}
        <span class="day">{mode === 'final' ? 'Final' : `Set ${live.set_no}${live.sets[0] || live.sets[1] ? ` · sets ${live.sets[0]}-${live.sets[1]}` : ''}`}</span>
      {:else}
        <span class="time">{match.starts_at ? formatTime(match.starts_at) : 'VS'}</span>
        <span class="day">{formatDay(match.starts_at)}</span>
      {/if}
    </div>
    <div class="team">
      <TeamBadge name={match.away} logo={match.away_logo} size={52} />
      <span class="name">{shortTeam(match.away)}</span>
    </div>
  </div>

  {#if match.schedule_override && !mode}
    <p class="club-note">Horario confirmado por el club</p>
  {/if}
  {#if match.starts_at && !mode}
    <div class="countdown"><Countdown iso={match.starts_at} /></div>
    <div class="weather"><WeatherChip {match} tone="dark" /></div>
  {/if}

  {#if match.cheers?.open}
    <CheerBar {match} />
  {/if}

  <footer>
    {#if match.venue}
      <a class="venue" href={today ? directionsUrl(match.venue) : mapsUrl(match.venue)} target="_blank" rel="noopener">
        <Icon name="pin" size={16} />
        <span class="venue-text">{match.venue}</span>
      </a>
    {:else}
      <span class="venue"><Icon name="pin" size={16} /> Pabellón por confirmar</span>
    {/if}
    {#if (today || mode) && match.live_id}
      <button class="live-btn" class:on={mode === 'live'} onclick={() => go(`/directo/${match.live_id}`)}>
        <i aria-hidden="true"></i> {mode === 'final' ? 'Ver final' : 'Ver en directo'}
      </button>
      <button class="icon-btn" onclick={() => go(`/marcador?pick=${match.id}`)} aria-label="Llevar el marcador" title="Llevar el marcador">
        <Icon name="score" size={18} />
      </button>
    {/if}
    <button class="share" onclick={() => openShare(dataFromMatch(match, category), matchText(category, match))} aria-label="Compartir partido">
      <Icon name="share" size={18} />
    </button>
  </footer>
</article>

<style>
  .next {
    position: relative;
    overflow: hidden;
    border-radius: var(--radius);
    padding: 16px;
    color: #fff;
    background:
      radial-gradient(120% 90% at 100% 0%, rgba(49, 169, 67, 0.55), transparent 60%),
      linear-gradient(160deg, #143a1f, #0b1a10);
    box-shadow: 0 10px 30px rgba(11, 26, 16, 0.35);
  }
  .next::after {
    /* balón decorativo */
    content: '';
    position: absolute;
    right: -40px;
    bottom: -40px;
    width: 160px;
    height: 160px;
    border-radius: 50%;
    border: 18px solid rgba(255, 255, 255, 0.04);
    pointer-events: none;
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  .label {
    color: #8ee39c;
  }
  /* Partido de hoy: borde que brilla con un pulso */
  .today {
    animation: glow 2.2s ease-in-out infinite;
  }
  @keyframes glow {
    0%,
    100% {
      box-shadow: 0 0 0 2px rgba(142, 227, 156, 0.95), 0 10px 30px rgba(11, 26, 16, 0.35);
    }
    50% {
      box-shadow: 0 0 0 5px rgba(142, 227, 156, 0.35), 0 0 30px rgba(49, 169, 67, 0.65);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .today {
      animation: none;
      box-shadow: 0 0 0 3px rgba(142, 227, 156, 0.9);
    }
  }
  .round {
    opacity: 0.7;
  }
  .round.shift {
    opacity: 1;
    color: #ffcf6e;
  }
  .teams {
    display: grid;
    grid-template-columns: 1fr auto 1fr;
    align-items: start;
    gap: 8px;
    margin: 16px 0 14px;
  }
  .team {
    display: grid;
    justify-items: center;
    gap: 8px;
    text-align: center;
    min-width: 0;
  }
  .name {
    font-weight: 700;
    font-size: 14.5px;
    line-height: 1.2;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .vs {
    display: grid;
    justify-items: center;
    padding-top: 8px;
  }
  .time {
    font-size: 26px;
    font-weight: 800;
    font-variant-numeric: tabular-nums;
  }
  .day {
    font-size: 13px;
    opacity: 0.8;
  }
  .club-note {
    margin: -4px 0 10px;
    text-align: center;
    font-size: 12.5px;
    font-weight: 700;
    color: #8ee39c;
  }
  .countdown {
    display: flex;
    justify-content: center;
    margin-bottom: 14px;
  }
  .weather:not(:empty) {
    margin-bottom: 14px;
  }
  footer {
    display: flex;
    align-items: center;
    gap: 10px;
    padding-top: 12px;
    border-top: 1px solid rgba(255, 255, 255, 0.1);
  }
  .venue {
    flex: 1;
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 6px;
    color: rgba(255, 255, 255, 0.85);
    font-size: 14px;
    text-decoration: none;
  }
  .venue :global(svg) {
    flex: none;
  }
  .venue-text {
    min-width: 0;
    overflow-wrap: anywhere;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .time.score {
    color: #8ee39c;
  }
  /* Botón al visor en directo: el punto rojo late si se está retransmitiendo */
  .live-btn {
    flex: none;
    display: inline-flex;
    align-items: center;
    gap: 7px;
    height: 40px;
    padding: 0 14px;
    border-radius: 999px;
    background: #fff;
    color: #0b1a10;
    font-weight: 800;
    font-size: 14px;
    transition: transform 0.15s;
  }
  .live-btn:active {
    transform: scale(0.95);
  }
  .live-btn i {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #9aa5a0;
  }
  .live-btn.on {
    color: #d92d33;
  }
  .live-btn.on i {
    background: #ff3b41;
    animation: blink 1s infinite;
  }
  @keyframes blink {
    50% {
      opacity: 0.25;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .live-btn.on i {
      animation: none;
    }
  }
  .icon-btn,
  .share {
    flex: none;
    width: 40px;
    height: 40px;
    border-radius: 50%;
    display: grid;
    place-items: center;
    color: #fff;
    background: rgba(255, 255, 255, 0.12);
    transition: transform 0.15s;
  }
  .icon-btn:active,
  .share:active {
    transform: scale(0.9);
  }
</style>
