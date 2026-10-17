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
      .slice(0, 3)
      .map(([id]) => KINDS.find((k) => k.id === id)?.emoji)
      .filter(Boolean),
  );

  // Menú de ánimos: se abre con el corazón y se cierra solo tras unos segundos sin usarlo
  let open = $state(false);
  let wrap;
  let idle;
  function keepOpen() {
    clearTimeout(idle);
    idle = setTimeout(() => (open = false), 4000);
  }
  function toggle() {
    open = !open;
    if (open) keepOpen();
    else clearTimeout(idle);
  }
  $effect(() => {
    if (!open) return;
    const outside = (e) => !wrap?.contains(e.target) && (open = false);
    const esc = (e) => e.key === 'Escape' && (open = false);
    document.addEventListener('pointerdown', outside);
    document.addEventListener('keydown', esc);
    return () => {
      document.removeEventListener('pointerdown', outside);
      document.removeEventListener('keydown', esc);
      clearTimeout(idle);
    };
  });

  let particles = $state([]);
  let seq = 0;
  function send(kind) {
    cheer(match, kind.id);
    navigator.vibrate?.(8);
    keepOpen();
    if (reduced) return;
    const p = { id: ++seq, emoji: kind.emoji, x: Math.round(Math.random() * 50 - 40), r: Math.round(Math.random() * 40 - 20) };
    particles = [...particles.slice(-20), p];
    setTimeout(() => (particles = particles.filter((q) => q.id !== p.id)), 1200);
  }
</script>

<div class="cheers">
  <p class="count" aria-live="polite">
    <span class="heart-mini" aria-hidden="true">💚</span>
    {#key totals.total}<b class="num">{totals.total}</b>{/key}
    {totals.total === 1 ? 'ánimo' : 'ánimos'}
    {#if top.length}<span class="top" aria-hidden="true">{top.join('')}</span>{/if}
  </p>

  <div class="dial" bind:this={wrap}>
    {#if open}
      <ul class="menu" role="menu" aria-label="Elige un ánimo">
        {#each KINDS as k, i (k.id)}
          <li role="none" style="--i:{KINDS.length - 1 - i}">
            <button role="menuitem" onclick={() => send(k)}>
              <span class="em" aria-hidden="true">{k.emoji}</span>{k.label}
            </button>
          </li>
        {/each}
      </ul>
    {/if}
    <button
      class="heart"
      class:open
      onclick={toggle}
      aria-expanded={open}
      aria-haspopup="menu"
      aria-label={open ? 'Cerrar ánimos' : 'Enviar ánimos a Ancares'}
    >
      <span aria-hidden="true">{open ? '✕' : '💚'}</span>
    </button>
    <div class="particles" aria-hidden="true">
      {#each particles as p (p.id)}
        <span class="particle" style="--x:{p.x}px; --r:{p.r}deg">{p.emoji}</span>
      {/each}
    </div>
  </div>
</div>

<style>
  .cheers {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 14px;
  }
  .count {
    margin: 0;
    display: flex;
    align-items: baseline;
    gap: 5px;
    font-size: 14px;
    color: rgba(255, 255, 255, 0.85);
    min-width: 0;
  }
  .heart-mini {
    font-size: 15px;
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
    margin-left: 4px;
    letter-spacing: 1px;
  }

  .dial {
    position: relative;
    flex: none;
  }
  .heart {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    display: grid;
    place-items: center;
    font-size: 22px;
    color: #0b1a10;
    background: #fff;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.3);
    animation: beat 1.6s ease-in-out infinite;
    transition: transform 0.15s, background 0.2s;
    touch-action: manipulation;
  }
  .heart:active {
    transform: scale(0.9);
  }
  .heart.open {
    animation: none;
    background: rgba(255, 255, 255, 0.85);
    font-size: 18px;
    font-weight: 800;
  }
  @keyframes beat {
    0%,
    100% {
      transform: scale(1);
    }
    12% {
      transform: scale(1.12);
    }
    24% {
      transform: scale(1);
    }
  }

  /* Menú que se despliega encima del corazón */
  .menu {
    position: absolute;
    right: 0;
    bottom: 58px;
    z-index: 5;
    margin: 0;
    padding: 0;
    list-style: none;
    display: grid;
    justify-items: end;
    gap: 6px;
  }
  .menu li {
    animation: in 0.28s cubic-bezier(0.2, 1.3, 0.4, 1) both;
    animation-delay: calc(var(--i) * 35ms);
  }
  @keyframes in {
    from {
      opacity: 0;
      transform: translateY(12px) scale(0.85);
    }
  }
  .menu button {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 8px 14px 8px 10px;
    border-radius: 999px;
    background: #fff;
    color: #0b1a10;
    font-size: 14px;
    font-weight: 700;
    white-space: nowrap;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.25);
    transition: transform 0.12s;
    touch-action: manipulation;
  }
  .menu button:active {
    transform: scale(0.94);
  }
  .em {
    font-size: 18px;
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
    font-size: 24px;
    animation: rise 1.15s cubic-bezier(0.2, 0.8, 0.3, 1) forwards;
  }
  @keyframes rise {
    from {
      transform: translate(-50%, 0) scale(0.6) rotate(0deg);
      opacity: 1;
    }
    to {
      transform: translate(calc(-50% + var(--x)), -120px) scale(1.2) rotate(var(--r));
      opacity: 0;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .heart,
    .num,
    .menu li {
      animation: none;
    }
  }
</style>
