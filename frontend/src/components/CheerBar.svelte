<script>
  import { KINDS, cheer, cheerTotals, matchKey } from '../lib/cheers.js';
  import { reduced } from '../lib/motion.js';

  let { match } = $props();

  const key = $derived(matchKey(match));
  // Lo más reciente entre lo que trae la portada y lo que ya sabemos tras animar
  const totals = $derived.by(() => {
    const local = $cheerTotals[key];
    const server = match.cheers || { total: 0, by_kind: {} };
    return local && local.total >= server.total ? local : server;
  });
  const top = $derived(
    Object.entries(totals.by_kind || {})
      .sort((a, b) => b[1] - a[1])
      .slice(0, 2)
      .map(([id]) => KINDS.find((k) => k.id === id))
      .filter(Boolean),
  );

  let particles = $state([]);
  let seq = 0;

  function tap(kind) {
    cheer(match, kind.id);
    navigator.vibrate?.(8);
    if (reduced) return;
    const p = { id: ++seq, emoji: kind.emoji, x: Math.round(Math.random() * 80 - 40), r: Math.round(Math.random() * 40 - 20) };
    particles = [...particles.slice(-24), p];
    setTimeout(() => (particles = particles.filter((q) => q.id !== p.id)), 1200);
  }
</script>

<div class="cheers">
  <div class="main-wrap">
    <button class="main" onclick={() => tap(KINDS[0])}>
      <span class="heart">💚</span> ¡Vamos Ancares!
    </button>
    <div class="particles" aria-hidden="true">
      {#each particles as p (p.id)}
        <span class="particle" style="--x:{p.x}px; --r:{p.r}deg">{p.emoji}</span>
      {/each}
    </div>
  </div>

  <div class="chips">
    {#each KINDS.slice(1) as k}
      <button class="chip-btn" onclick={() => tap(k)}>{k.emoji} {k.label}</button>
    {/each}
  </div>

  <p class="count" aria-live="polite">
    {#key totals.total}<b class="num">{totals.total}</b>{/key}
    {totals.total === 1 ? 'ánimo' : 'ánimos'} para Ancares
    {#if top.length}<span class="top"> · {top.map((k) => k.emoji).join(' ')}</span>{/if}
  </p>
</div>

<style>
  .cheers {
    display: grid;
    gap: 10px;
    margin-bottom: 14px;
  }
  .main-wrap {
    position: relative;
  }
  .main {
    width: 100%;
    min-height: 52px;
    border-radius: 999px;
    background: #fff;
    color: #1f7f30;
    font-size: 17px;
    font-weight: 850;
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.25);
    animation: breathe 2.4s ease-in-out infinite;
    transition: transform 0.12s;
    touch-action: manipulation;
  }
  .main:active {
    transform: scale(0.95);
  }
  .heart {
    display: inline-block;
    animation: beat 1.2s ease-in-out infinite;
  }
  @keyframes breathe {
    50% {
      box-shadow: 0 6px 28px rgba(142, 227, 156, 0.55);
    }
  }
  @keyframes beat {
    0%,
    100% {
      transform: scale(1);
    }
    15% {
      transform: scale(1.25);
    }
    30% {
      transform: scale(1);
    }
  }
  .particles {
    position: absolute;
    left: 50%;
    top: 0;
    pointer-events: none;
  }
  .particle {
    position: absolute;
    left: 0;
    top: 0;
    font-size: 26px;
    animation: rise 1.15s cubic-bezier(0.2, 0.8, 0.3, 1) forwards;
  }
  @keyframes rise {
    from {
      transform: translate(-50%, 0) scale(0.6) rotate(0deg);
      opacity: 1;
    }
    to {
      transform: translate(calc(-50% + var(--x)), -110px) scale(1.25) rotate(var(--r));
      opacity: 0;
    }
  }
  .chips {
    display: flex;
    gap: 6px;
    overflow-x: auto;
    scrollbar-width: none;
    padding-bottom: 2px;
  }
  .chips::-webkit-scrollbar {
    display: none;
  }
  .chip-btn {
    flex: none;
    padding: 7px 12px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.14);
    color: #fff;
    font-size: 13.5px;
    font-weight: 700;
    white-space: nowrap;
    transition: transform 0.12s, background 0.2s;
    touch-action: manipulation;
  }
  .chip-btn:active {
    transform: scale(0.94);
    background: rgba(255, 255, 255, 0.24);
  }
  .count {
    margin: 0;
    text-align: center;
    font-size: 14px;
    color: rgba(255, 255, 255, 0.85);
  }
  .num {
    display: inline-block;
    font-size: 18px;
    color: #fff;
    font-variant-numeric: tabular-nums;
    animation: pop 0.3s ease-out;
  }
  @keyframes pop {
    from {
      transform: scale(1.4);
    }
  }
  .top {
    letter-spacing: 2px;
  }
  @media (prefers-reduced-motion: reduce) {
    .main,
    .heart,
    .num {
      animation: none;
    }
  }
</style>
