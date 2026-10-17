<script>
  import { formatTime, isOursName, shortTeam } from '../lib/format.js';
  import { pop, reduced } from '../lib/motion.js';

  /** today: [{ match, category }] partidos de Ancares de hoy, ya ordenados por hora */
  let { today } = $props();

  const rival = (m) => (isOursName(m.home) ? m.away : m.home);
  const line = $derived(
    today.length === 1
      ? `${formatTime(today[0].match.starts_at)} vs ${shortTeam(rival(today[0].match))}`
      : `${today.length} partidos: ${today.map((t) => formatTime(t.match.starts_at)).join(', ').replace(/, ([^,]*)$/, ' y $1')}`,
  );

  // Al tocar el aviso, baja hasta la tarjeta del primer partido del día
  function goToMatch() {
    document.getElementById(`match-${today[0].match.id}`)?.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'center' });
  }
</script>

<button class="banner" in:pop onclick={goToMatch}>
  <span class="ball" aria-hidden="true">🏐</span>
  <span class="text">
    <b>¡HOY JUEGA ANCARES!</b>
    <span>{line}</span>
  </span>
  <span class="arrow" aria-hidden="true">↓</span>
</button>

<style>
  .banner {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    margin-bottom: 18px;
    border-radius: var(--radius);
    color: #fff;
    text-align: left;
    background: linear-gradient(120deg, #1f7f30, #31a943, #1d6b2a, #2f9e40);
    background-size: 300% 300%;
    animation: flow 9s ease infinite;
    box-shadow: 0 8px 24px rgba(31, 127, 48, 0.35);
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
  .ball {
    font-size: 32px;
    animation: bounce 1.1s cubic-bezier(0.3, 0, 0.4, 1) infinite;
    filter: drop-shadow(0 5px 3px rgba(0, 0, 0, 0.25));
  }
  @keyframes bounce {
    0%,
    100% {
      transform: translateY(0) rotate(0deg);
    }
    50% {
      transform: translateY(-9px) rotate(180deg);
    }
  }
  .text {
    flex: 1;
    min-width: 0;
    display: grid;
  }
  .text b {
    font-size: 19px;
    font-weight: 900;
    letter-spacing: 0.01em;
  }
  .text span {
    font-size: 13.5px;
    opacity: 0.9;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .arrow {
    font-size: 20px;
    font-weight: 800;
    opacity: 0.85;
    animation: nudge 1.6s ease-in-out infinite;
  }
  @keyframes nudge {
    50% {
      transform: translateY(4px);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .banner,
    .ball,
    .arrow {
      animation: none;
    }
  }
</style>
