<script>
  import { onMount } from 'svelte';
  import Icon from './Icon.svelte';
  import TeamBadge from './TeamBadge.svelte';
  import { directionsUrl, formatTime, isOursName, matchState, shortTeam, timeUntil } from '../lib/format.js';
  import { matchText } from '../lib/share.js';
  import { dataFromMatch } from '../lib/shareData.js';
  import { openShare } from '../lib/shareSheet.js';
  import { go } from '../lib/router.js';
  import { pop } from '../lib/motion.js';

  /** today: [{ match, category }] partidos de Ancares de hoy */
  let { today } = $props();

  let now = $state(Date.now());
  onMount(() => {
    const t = setInterval(() => (now = Date.now()), 30000);
    return () => clearInterval(t);
  });

  const rival = (m) => (isOursName(m.home) ? m.away : m.home);
  const rivalLogo = (m) => (isOursName(m.home) ? m.away_logo : m.home_logo);
</script>

<section class="banner" in:pop>
  <div class="title">
    <span class="ball" aria-hidden="true">🏐</span>
    <div>
      <span class="kicker">Día de partido</span>
      <h2>¡HOY JUEGA ANCARES!</h2>
    </div>
  </div>

  {#each today as { match: m, category } (m.id)}
    {@const state = matchState(m.starts_at, now)}
    <div class="row">
      <div class="info">
        <TeamBadge name={rival(m)} logo={rivalLogo(m)} size={38} />
        <div class="text">
          <b class="ellipsis">{formatTime(m.starts_at)} · vs {shortTeam(rival(m))}</b>
          <span class="ellipsis">
            {category}
            {#if state === 'live'}· <span class="live"><i></i> En juego</span>
            {:else if state === 'upcoming'}· {timeUntil(m.starts_at, now)}
            {:else}· Terminado{/if}
          </span>
        </div>
      </div>
      <div class="actions">
        {#if m.venue}
          <a class="act" href={directionsUrl(m.venue)} target="_blank" rel="noopener"><Icon name="pin" size={16} /> Cómo llegar</a>
        {/if}
        <button class="act" onclick={() => go(`/marcador?pick=${m.id}`)}><Icon name="score" size={16} /> Marcador</button>
        <button class="act" onclick={() => openShare(dataFromMatch(m, category), matchText(category, m))} aria-label="Compartir previa">
          <Icon name="share" size={16} />
        </button>
      </div>
    </div>
  {/each}
</section>

<style>
  .banner {
    position: relative;
    overflow: hidden;
    display: grid;
    gap: 12px;
    padding: 16px;
    margin-bottom: 18px;
    border-radius: var(--radius);
    color: #fff;
    background: linear-gradient(120deg, #1f7f30, #31a943, #1d6b2a, #2f9e40);
    background-size: 300% 300%;
    animation: flow 9s ease infinite;
    box-shadow: 0 10px 30px rgba(31, 127, 48, 0.35);
  }
  @keyframes flow {
    0%,
    100% {
      background-position: 0% 50%;
    }
    50% {
      background-position: 100% 50%;
    }
  }
  .title {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .ball {
    font-size: 38px;
    animation: bounce 1.1s cubic-bezier(0.3, 0, 0.4, 1) infinite;
    filter: drop-shadow(0 6px 4px rgba(0, 0, 0, 0.25));
  }
  @keyframes bounce {
    0%,
    100% {
      transform: translateY(0) rotate(0deg);
    }
    50% {
      transform: translateY(-12px) rotate(180deg);
    }
  }
  .kicker {
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    opacity: 0.85;
  }
  h2 {
    font-size: 23px;
    font-weight: 900;
    letter-spacing: 0.01em;
  }
  .row {
    display: grid;
    gap: 10px;
    padding: 12px;
    border-radius: 14px;
    background: rgba(0, 0, 0, 0.16);
  }
  .info {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
  }
  .text {
    display: grid;
    min-width: 0;
    font-size: 13.5px;
  }
  .text b {
    font-size: 16px;
  }
  .live {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-weight: 800;
  }
  .live i {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #ff5a5f;
    animation: blink 1s infinite;
  }
  @keyframes blink {
    50% {
      opacity: 0.25;
    }
  }
  .actions {
    display: flex;
    gap: 8px;
  }
  .act {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    min-height: 38px;
    padding: 0 12px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.18);
    color: #fff;
    font-size: 13.5px;
    font-weight: 700;
    text-decoration: none;
    flex: 1 1 auto;
  }
  .act:last-child {
    flex: none;
    width: 38px;
    padding: 0;
  }
  @media (prefers-reduced-motion: reduce) {
    .banner,
    .ball,
    .live i {
      animation: none;
    }
  }
</style>
