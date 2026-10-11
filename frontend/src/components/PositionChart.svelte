<script>
  import { onMount } from 'svelte';
  import { shortTeam } from '../lib/format.js';
  import { reduced } from '../lib/motion.js';

  /** rounds: [{round_no, round_name}], teams: [{team, is_ours, positions[], points[]}] */
  let { rounds = [], teams = [], total = 0 } = $props();

  const W = 340;
  const H = 210;
  const M = { top: 14, right: 40, bottom: 26, left: 30 };
  const iw = W - M.left - M.right;
  const ih = H - M.top - M.bottom;

  const n = $derived(Math.max(total, ...teams.map((t) => Math.max(...t.positions, 1))));
  const x = (i) => M.left + (rounds.length > 1 ? (i / (rounds.length - 1)) * iw : iw / 2);
  const y = (pos) => M.top + (n > 1 ? ((pos - 1) / (n - 1)) * ih : ih / 2);
  const path = (positions) => positions.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p).toFixed(1)}`).join(' ');

  const ours = $derived(teams.find((t) => t.is_ours));
  const others = $derived(teams.filter((t) => !t.is_ours));
  const yTicks = $derived([...new Set([1, Math.ceil(n / 2), n])]);
  // Etiquetas del eje X sin amontonarse: como mucho ~8
  const xStep = $derived(Math.max(1, Math.ceil(rounds.length / 8)));

  // Animación de trazado de la línea de Ancares
  let drawn = $state(reduced);
  onMount(() => requestAnimationFrame(() => (drawn = true)));

  // Punto de referencia: jornada más cercana al dedo/cursor
  let svg;
  let active = $state(null);
  function pick(e) {
    const rect = svg.getBoundingClientRect();
    const px = ((e.clientX - rect.left) / rect.width) * W;
    let best = 0;
    rounds.forEach((_, i) => {
      if (Math.abs(x(i) - px) < Math.abs(x(best) - px)) best = i;
    });
    active = best;
  }
  const leaderAt = (i) => teams.find((t) => t.positions[i] === 1);
  // En táctil el detalle se queda hasta tocar fuera de la gráfica
  $effect(() => {
    if (active === null) return;
    const away = (e) => !svg?.contains(e.target) && (active = null);
    document.addEventListener('pointerdown', away);
    return () => document.removeEventListener('pointerdown', away);
  });
</script>

<div class="chart">
  <div class="legend" aria-hidden="true">
    <span class="key ours"><i></i> {ours ? shortTeam(ours.team) : 'Ancares'}</span>
    <span class="key rest"><i></i> Resto de equipos</span>
  </div>

  <div class="plot">
    <svg
      bind:this={svg}
      viewBox="0 0 {W} {H}"
      role="img"
      aria-label="Posición de {ours ? shortTeam(ours.team) : 'Ancares'} por jornada"
      onpointerdown={pick}
      onpointermove={pick}
      onpointerleave={(e) => e.pointerType === 'mouse' && (active = null)}
    >
      <!-- rejilla y eje Y (1º arriba) -->
      {#each yTicks as t}
        <line class="grid" x1={M.left} x2={W - M.right} y1={y(t)} y2={y(t)} />
        <text class="tick" x={M.left - 8} y={y(t) + 4} text-anchor="end">{t}º</text>
      {/each}
      {#each rounds as r, i}
        {#if i % xStep === 0 || i === rounds.length - 1}
          <text class="tick" x={x(i)} y={H - 8} text-anchor="middle">J{r.round_no}</text>
        {/if}
      {/each}

      <!-- resto de equipos: contexto atenuado -->
      {#each others as t}
        <path class="other" d={path(t.positions)} />
      {/each}

      {#if active !== null}
        <line class="cross" x1={x(active)} x2={x(active)} y1={M.top - 6} y2={H - M.bottom} />
      {/if}

      {#if ours}
        <path class="ours-line" class:drawn d={path(ours.positions)} pathLength="1" />
        {#each ours.positions as p, i}
          <circle class="dot" class:on={active === i} cx={x(i)} cy={y(p)} r={active === i ? 6 : 4.5} />
        {/each}
        <text class="end-label" x={x(ours.positions.length - 1) + 10} y={y(ours.positions.at(-1)) + 5}>
          {ours.positions.at(-1)}º
        </text>
      {/if}
    </svg>

  </div>

  <!-- Lectura de la jornada tocada: debajo de la gráfica para no tapar nada -->
  <p class="readout" aria-live="polite">
    {#if active !== null && ours}
      {@const leader = leaderAt(active)}
      <b>{rounds[active].round_name}:</b> {ours.positions[active]}º · {ours.points[active]} pts
      {#if leader && !leader.is_ours}<span class="muted"> · líder {shortTeam(leader.team)} ({leader.points[active]} pts)</span>{/if}
    {:else}
      <span class="muted">Toca la gráfica para ver cada jornada</span>
    {/if}
  </p>

  {#if ours}
    <details class="table-view">
      <summary>Ver los datos</summary>
      <table>
        <thead><tr><th>Jornada</th><th>Posición</th><th>Puntos</th></tr></thead>
        <tbody>
          {#each rounds as r, i}
            <tr><td>{r.round_name}</td><td>{ours.positions[i]}º</td><td>{ours.points[i]}</td></tr>
          {/each}
        </tbody>
      </table>
    </details>
  {/if}
</div>

<style>
  .chart {
    --series: var(--brand-strong);
    display: grid;
    gap: 6px;
  }
  @media (prefers-color-scheme: dark) {
    .chart {
      --series: var(--brand);
    }
  }
  .legend {
    display: flex;
    gap: 14px;
    font-size: 12.5px;
    color: var(--muted);
  }
  .key {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  .key i {
    width: 16px;
    height: 3px;
    border-radius: 2px;
  }
  .key.ours i {
    background: var(--series);
  }
  .key.rest i {
    height: 2px;
    background: var(--muted);
    opacity: 0.45;
  }
  .plot {
    position: relative;
  }
  svg {
    display: block;
    width: 100%;
    height: auto;
    touch-action: pan-y;
    overflow: visible;
  }
  .grid {
    stroke: var(--line);
    stroke-width: 1;
  }
  .tick {
    font-size: 10.5px;
    fill: var(--muted);
    font-variant-numeric: tabular-nums;
  }
  .other {
    fill: none;
    stroke: var(--muted);
    stroke-width: 1.5;
    stroke-opacity: 0.28;
    stroke-linejoin: round;
    stroke-linecap: round;
  }
  .cross {
    stroke: var(--muted);
    stroke-width: 1;
    stroke-dasharray: 3 3;
  }
  .ours-line {
    fill: none;
    stroke: var(--series);
    stroke-width: 3;
    stroke-linejoin: round;
    stroke-linecap: round;
    stroke-dasharray: 1;
    stroke-dashoffset: 1;
    transition: stroke-dashoffset 1.1s cubic-bezier(0.3, 0.8, 0.3, 1);
  }
  .ours-line.drawn {
    stroke-dashoffset: 0;
  }
  .dot {
    fill: var(--series);
    stroke: var(--surface);
    stroke-width: 2;
    transition: r 0.15s;
  }
  .end-label {
    font-size: 12px;
    font-weight: 800;
    fill: var(--text);
  }
  .readout {
    margin: 0;
    min-height: 20px;
    font-size: 13px;
    text-align: center;
    font-variant-numeric: tabular-nums;
  }
  .muted {
    color: var(--muted);
  }
  .table-view summary {
    font-size: 13px;
    color: var(--muted);
    cursor: pointer;
  }
  table {
    width: 100%;
    margin-top: 8px;
    border-collapse: collapse;
    font-size: 13px;
    font-variant-numeric: tabular-nums;
  }
  th,
  td {
    text-align: left;
    padding: 4px 6px;
    border-bottom: 1px solid var(--line);
  }
  th {
    color: var(--muted);
    font-weight: 650;
  }
</style>
