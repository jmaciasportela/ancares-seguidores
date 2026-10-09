<script>
  import { flip } from 'svelte/animate';
  import TeamBadge from './TeamBadge.svelte';
  import { shortTeam } from '../lib/format.js';
  import { flipOpts, fly } from '../lib/motion.js';

  let { standings = [] } = $props();
</script>

<div class="table card" role="table" aria-label="Clasificación">
  <div class="tr head" role="row">
    <span role="columnheader" class="pos">#</span>
    <span role="columnheader" class="team">Equipo</span>
    <span role="columnheader" title="Puntos">Pts</span>
    <span role="columnheader" title="Partidos jugados">PJ</span>
    <span role="columnheader" title="Ganados">G</span>
    <span role="columnheader" title="Perdidos">P</span>
    <span role="columnheader" class="sets" title="Sets a favor - en contra">Sets</span>
  </div>
  {#each standings as s, i (s.team)}
    <div
      class="tr"
      class:ours={s.is_ours}
      role="row"
      animate:flip={flipOpts}
      in:fly={{ y: 10, delay: Math.min(i * 35, 400) }}
    >
      <span role="cell" class="pos"><b class="n" class:top={s.position <= 3}>{s.position}</b></span>
      <span role="cell" class="team">
        <TeamBadge name={s.team} size={26} />
        <span class="ellipsis">{shortTeam(s.team)}</span>
      </span>
      <span role="cell" class="pts">{s.points}</span>
      <span role="cell">{s.played}</span>
      <span role="cell">{s.won}</span>
      <span role="cell">{s.lost}</span>
      <span role="cell" class="sets">{s.sets_for}-{s.sets_against}</span>
    </div>
  {/each}
</div>

<style>
  .table {
    overflow: hidden;
    padding: 4px 0;
  }
  .tr {
    display: grid;
    grid-template-columns: 34px minmax(0, 1fr) 36px 28px 26px 26px 50px;
    align-items: center;
    gap: 4px;
    padding: 9px 12px;
    font-size: 14.5px;
    font-variant-numeric: tabular-nums;
    text-align: center;
  }
  .tr + .tr {
    border-top: 1px solid var(--line);
  }
  .head {
    font-size: 12px;
    font-weight: 700;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding-top: 10px;
    padding-bottom: 8px;
  }
  .team {
    display: flex;
    align-items: center;
    gap: 8px;
    text-align: left;
    min-width: 0;
  }
  .pts {
    font-weight: 800;
  }
  .sets {
    color: var(--muted);
    font-size: 13px;
  }
  .n {
    display: inline-grid;
    place-items: center;
    width: 24px;
    height: 24px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 750;
  }
  .n.top {
    background: var(--surface-2);
  }
  .ours {
    background: var(--brand-soft);
    font-weight: 700;
    position: relative;
  }
  .ours::before {
    content: '';
    position: absolute;
    left: 0;
    top: 6px;
    bottom: 6px;
    width: 4px;
    border-radius: 0 4px 4px 0;
    background: var(--brand);
  }
  .ours .n {
    background: var(--brand);
    color: #fff;
  }
  @media (max-width: 360px) {
    .tr {
      grid-template-columns: 30px minmax(0, 1fr) 34px 26px 24px 24px;
      padding: 9px 8px;
    }
    .sets {
      display: none;
    }
  }
</style>
