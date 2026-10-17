<script>
  import { onDestroy } from 'svelte';
  import TeamBadge from './TeamBadge.svelte';
  import { resource } from '../lib/api.js';
  import { isOursName, ourOutcome, partialsText, scoreOf, shortTeam } from '../lib/format.js';
  import { fade, pop, reduced } from '../lib/motion.js';
  import { route } from '../lib/router.js';
  import { matchText } from '../lib/share.js';
  import { dataFromMatch } from '../lib/shareData.js';
  import { openShare } from '../lib/shareSheet.js';

  const RECENT = 48 * 3600e3;
  const home = resource('/api/home');

  const seenKey = (cat, m, s) => `ancares:celebrated:${cat.id}|${m.round_no}|${m.home}|${m.away}|${s.home}-${s.away}`;
  function seen(k) {
    try {
      return !!localStorage.getItem(k);
    } catch {
      return true; // sin almacenamiento, mejor no repetir la celebración en cada visita
    }
  }

  // Resultados recientes de Ancares que este móvil aún no ha celebrado
  const pending = $derived.by(() => {
    const out = [];
    for (const cat of $home.data?.categories || []) {
      const m = cat.last_result;
      if (!m) continue; // categoría sin resultados todavía
      const s = scoreOf(m);
      const age = m.starts_at ? Date.now() - new Date(m.starts_at).getTime() : null;
      // Solo partidos ya empezados (margen de 3 h) de las últimas 48 h
      if (!s || age === null || age < -3 * 3600e3 || age > RECENT) continue;
      const key = seenKey(cat, m, s);
      if (!seen(key)) out.push({ key, cat, m, s, outcome: ourOutcome(m, isOursName) });
    }
    return out;
  });
  const blocked = $derived(['admin', 'marcador', 'directo'].includes($route.parts[0]));
  let dismissed = $state([]);
  const current = $derived(blocked ? null : pending.find((p) => !dismissed.includes(p.key)) || null);

  function close() {
    if (!current) return;
    try {
      localStorage.setItem(current.key, '1');
    } catch {
      /* ignorado */
    }
    dismissed = [...dismissed, current.key];
  }

  function share() {
    const { m, cat } = current;
    close();
    openShare(dataFromMatch(m, cat.name), matchText(cat.name, m));
  }

  // --- confeti (solo victorias y sin «reducir movimiento») ---
  let canvas = $state();
  let frame;
  $effect(() => {
    if (!current || current.outcome !== true || reduced || !canvas) return;
    const ctx = canvas.getContext('2d');
    const dpr = Math.min(devicePixelRatio || 1, 2);
    canvas.width = innerWidth * dpr;
    canvas.height = innerHeight * dpr;
    ctx.scale(dpr, dpr);
    const colors = ['#31a943', '#ffffff', '#0b1a10', '#8ee39c', '#1f7f30'];
    const W = innerWidth;
    const H = innerHeight;
    const piece = (x, y, vx, vy) => ({
      x, y, vx, vy,
      w: 6 + Math.random() * 6,
      h: 8 + Math.random() * 8,
      rot: Math.random() * Math.PI,
      vr: (Math.random() - 0.5) * 0.3,
      sway: Math.random() * Math.PI * 2,
      color: colors[Math.floor(Math.random() * colors.length)],
    });
    // Explosión desde el centro y lluvia desde arriba que cae despacio
    const pieces = [
      ...Array.from({ length: 90 }, () => piece(W / 2, H * 0.32, (Math.random() - 0.5) * 16, -Math.random() * 14 - 4)),
      ...Array.from({ length: 110 }, () => piece(Math.random() * W, -Math.random() * H * 0.8, (Math.random() - 0.5) * 2, 2 + Math.random() * 2)),
    ];
    const DURATION = 4500;
    const start = performance.now();
    const step = (t) => {
      const elapsed = t - start;
      ctx.clearRect(0, 0, W, H);
      ctx.globalAlpha = Math.min(1, Math.max(0, (DURATION - elapsed) / 1000)); // se desvanece el último segundo
      for (const p of pieces) {
        p.vy = Math.min(p.vy + 0.22, 4.5); // velocidad máxima: cae como papel
        p.vx *= 0.97;
        p.sway += 0.08;
        p.x += p.vx + Math.sin(p.sway) * 0.8;
        p.y += p.vy;
        p.rot += p.vr;
        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate(p.rot);
        ctx.fillStyle = p.color;
        ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h * Math.abs(Math.cos(p.rot)));
        ctx.restore();
      }
      if (elapsed < DURATION) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  });
  onDestroy(() => cancelAnimationFrame(frame));
</script>

<svelte:window onkeydown={(e) => e.key === 'Escape' && close()} />

{#if current}
  {@const { m, s, cat, outcome } = current}
  <div class="overlay" class:win={outcome === true} transition:fade onclick={(e) => e.target === e.currentTarget && close()} role="presentation">
    <canvas bind:this={canvas} aria-hidden="true"></canvas>
    <div class="card" in:pop role="dialog" aria-modal="true" aria-labelledby="celebration-title" tabindex="-1">
      <span class="big" aria-hidden="true">{outcome === true ? '🏆' : outcome === false ? '💚' : '🤝'}</span>
      <h2 id="celebration-title">
        {outcome === true ? '¡VICTORIA!' : outcome === false ? '¡A por el siguiente!' : '¡Empate!'}
      </h2>
      {#if outcome === false}<p class="sub">Orgullosos de vosotras, ¡seguimos! 💪</p>{/if}
      <p class="meta">{cat.name} · {m.round_name}</p>
      <div class="score">
        <div class="team"><TeamBadge name={m.home} logo={m.home_logo} size={46} /><span>{shortTeam(m.home)}</span></div>
        <b>{s.home}–{s.away}</b>
        <div class="team"><TeamBadge name={m.away} logo={m.away_logo} size={46} /><span>{shortTeam(m.away)}</span></div>
      </div>
      {#if s.partials.length}<p class="partials">{partialsText(s)}</p>{/if}
      {#if s.provisional}<p class="prov">⏳ Resultado provisional</p>{/if}
      <div class="buttons">
        <button class="btn primary" onclick={share}>Compartir</button>
        <button class="btn ghost" onclick={close}>Cerrar</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .overlay {
    position: fixed;
    inset: 0;
    z-index: 80;
    display: grid;
    place-items: center;
    padding: 24px;
    background: rgba(5, 14, 8, 0.72);
    backdrop-filter: blur(4px);
  }
  canvas {
    position: fixed;
    inset: 0;
    width: 100vw;
    height: 100dvh;
    pointer-events: none;
  }
  .card {
    position: relative;
    width: min(100%, 380px);
    display: grid;
    justify-items: center;
    gap: 6px;
    padding: 24px 20px 20px;
    border-radius: 24px;
    background: var(--surface);
    color: var(--text);
    text-align: center;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
  }
  .win .card {
    background: linear-gradient(160deg, #1f7f30, #0b1a10);
    color: #fff;
  }
  .big {
    font-size: 54px;
    line-height: 1;
    animation: wobble 1.4s ease-in-out infinite;
  }
  @keyframes wobble {
    0%,
    100% {
      transform: rotate(-8deg) scale(1);
    }
    50% {
      transform: rotate(8deg) scale(1.08);
    }
  }
  h2 {
    font-size: 30px;
    font-weight: 900;
  }
  .sub,
  .meta,
  .partials,
  .prov {
    margin: 0;
    font-size: 14px;
  }
  .meta {
    opacity: 0.75;
  }
  .score {
    display: grid;
    grid-template-columns: 1fr auto 1fr;
    align-items: center;
    gap: 10px;
    width: 100%;
    margin: 8px 0 2px;
  }
  .team {
    display: grid;
    justify-items: center;
    gap: 6px;
    font-size: 13.5px;
    font-weight: 700;
    min-width: 0;
  }
  .team span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 100%;
  }
  .score b {
    font-size: 42px;
    font-weight: 900;
    font-variant-numeric: tabular-nums;
  }
  .partials {
    font-variant-numeric: tabular-nums;
    opacity: 0.85;
  }
  .prov {
    color: #f5b94a;
    font-weight: 700;
  }
  .buttons {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    width: 100%;
    margin-top: 12px;
  }
  .win .btn.ghost {
    color: #fff;
    border-color: rgba(255, 255, 255, 0.3);
  }
  @media (prefers-reduced-motion: reduce) {
    .big {
      animation: none;
    }
  }
</style>
