<script>
  import PositionChart from '../components/PositionChart.svelte';
  import { resource } from '../lib/api.js';
  import { shortTeam } from '../lib/format.js';
  import { fly } from '../lib/motion.js';

  let { slug } = $props();
  const res = $derived(resource(`/api/categories/${slug}/stats`));
  const data = $derived($res.data);
  const o = $derived(data?.ours);
  const LABEL = { W: 'V', L: 'D', D: 'E' };
  const TITLE = { W: 'Victoria', L: 'Derrota', D: 'Empate' };
  const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
</script>

{#if !data}
  <div class="skeleton" style="height:320px"></div>
{:else if !o || !o.played}
  <div class="card empty">
    <span class="big">📊</span>
    <p>Las estadísticas aparecerán cuando se juegue la primera jornada.</p>
  </div>
{:else}
  <section class="card streak" in:fly={{ y: 12 }}>
    <h3>Racha</h3>
    <div class="pills" role="list">
      {#each o.streak as s}
        <span
          class="pill {s.result}"
          class:prov={s.provisional}
          role="listitem"
          title="{TITLE[s.result]} {s.score} vs {s.rival} ({s.round_name}){s.provisional ? ' · provisional' : ''}"
        >{LABEL[s.result]}</span>
      {/each}
    </div>
    <span class="muted small">{o.streak.length === 1 ? 'Último partido' : `Últimos ${o.streak.length} partidos`}{o.has_provisional ? ' · en ámbar, provisionales' : ''}</span>
  </section>

  <section class="tiles" in:fly={{ y: 12, delay: 60 }}>
    <div class="tile card"><b>{o.position ?? '–'}º</b><span>de {o.teams}</span></div>
    <div class="tile card"><b>{o.points ?? 0}</b><span>puntos</span></div>
    <div class="tile card"><b>{o.sets_won_pct ?? '–'}%</b><span>sets ganados</span></div>
    <div class="tile card"><b>{o.avg_points_per_set ?? '–'}</b><span>puntos por set</span></div>
  </section>
  <p class="muted small balance">
    <span>{plural(o.played, 'partido', 'partidos')}</span> ·
    <span>{plural(o.won, 'victoria', 'victorias')}</span> ·
    <span>{plural(o.lost, 'derrota', 'derrotas')}</span> ·
    <span>sets {o.sets_for}-{o.sets_against}</span> ·
    <span>puntos {o.points_for}-{o.points_against}</span>
  </p>

  {#if data.rounds.length}
    <section class="card chart-card" in:fly={{ y: 12, delay: 120 }}>
      <h3>Posición por jornada</h3>
      <PositionChart rounds={data.rounds} teams={data.teams} total={o.teams} />
      {#if data.approximate}
        <p class="muted small">Evolución reconstruida con los resultados del calendario: puede no coincidir del todo con la clasificación oficial (sanciones, aplazamientos…).</p>
      {/if}
    </section>
  {/if}

  <section class="facts" in:fly={{ y: 12, delay: 180 }}>
    {#if o.longest_set}
      <div class="fact card">
        <span class="icon">⏱️</span>
        <div><b>Set más largo</b><span>{o.longest_set.score} vs {shortTeam(o.longest_set.rival)} · {o.longest_set.round_name}</span></div>
      </div>
    {/if}
    {#if o.clearest_win}
      <div class="fact card">
        <span class="icon">💪</span>
        <div><b>Victoria más clara</b><span>{o.clearest_win.score} vs {shortTeam(o.clearest_win.rival)} ({o.clearest_win.partials})</span></div>
      </div>
    {/if}
    {#if o.best_streak > 1}
      <div class="fact card">
        <span class="icon">🔥</span>
        <div><b>Mejor racha</b><span>{plural(o.best_streak, 'victoria', 'victorias')} seguidas</span></div>
      </div>
    {/if}
  </section>
{/if}

<style>
  section {
    margin-bottom: 12px;
  }
  h3 {
    font-size: 15px;
    font-weight: 800;
    margin-bottom: 10px;
  }
  .small {
    font-size: 12.5px;
  }
  .streak,
  .chart-card {
    padding: 14px 16px;
  }
  .pills {
    display: flex;
    gap: 8px;
    margin-bottom: 8px;
  }
  .pill {
    width: 40px;
    height: 40px;
    border-radius: 12px;
    display: grid;
    place-items: center;
    font-weight: 850;
    font-size: 17px;
    color: #fff;
  }
  .pill.W {
    background: var(--brand-strong);
  }
  .pill.L {
    background: var(--danger);
  }
  .pill.D {
    background: var(--muted);
  }
  .pill.prov {
    box-shadow: 0 0 0 3px var(--warn);
  }
  .tiles {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 8px;
    margin-bottom: 6px;
  }
  .tile {
    display: grid;
    justify-items: center;
    padding: 12px 4px;
    text-align: center;
  }
  .tile b {
    font-size: 22px;
    font-weight: 850;
    font-variant-numeric: tabular-nums;
  }
  .tile span {
    font-size: 11.5px;
    color: var(--muted);
  }
  .balance span {
    white-space: nowrap;
  }
  .balance {
    text-align: center;
    margin: 0 0 12px;
  }
  .facts {
    display: grid;
    gap: 8px;
  }
  .fact {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 14px;
  }
  .fact .icon {
    font-size: 24px;
  }
  .fact div {
    display: grid;
    font-size: 13.5px;
  }
  .fact div span {
    color: var(--muted);
  }
  .empty {
    display: grid;
    justify-items: center;
    gap: 6px;
    padding: 32px 20px;
    text-align: center;
    color: var(--muted);
  }
  .empty p {
    margin: 0;
  }
  .big {
    font-size: 36px;
  }
  @media (max-width: 360px) {
    .tiles {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }
</style>
