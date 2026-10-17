<script>
  import Icon from './Icon.svelte';
  import TeamBadge from './TeamBadge.svelte';
  import WeatherChip from './WeatherChip.svelte';
  import { directionsUrl, formatDay, formatTime, isOursName, isToday, mapsUrl, shortTeam } from '../lib/format.js';
  import TodayBadge from './TodayBadge.svelte';

  /** Tarjeta compacta para el partido que va después del próximo: versión pequeña de NextMatchCard. */
  let { match } = $props();
  const today = $derived(isToday(match.starts_at));
</script>

<article class="upcoming" class:today id="match-{match.id}">
  <header>
    <span class="label">Siguiente partido</span>
    {#if today}<TodayBadge startsAt={match.starts_at} />{:else}<span class="round">{match.round_name}</span>{/if}
  </header>

  <div class="teams">
    <div class="team" class:ours={isOursName(match.home)}>
      <TeamBadge name={match.home} logo={match.home_logo} size={44} />
      <span class="name">{shortTeam(match.home)}</span>
    </div>
    <div class="when">
      <span class="day">{formatDay(match.starts_at)}</span>
      {#if match.starts_at}<b class="time">{formatTime(match.starts_at)}</b>{:else}<b class="time vs">VS</b>{/if}
    </div>
    <div class="team" class:ours={isOursName(match.away)}>
      <TeamBadge name={match.away} logo={match.away_logo} size={44} />
      <span class="name">{shortTeam(match.away)}</span>
    </div>
  </div>

  <footer>
    {#if match.venue}
      <a class="venue" href={today ? directionsUrl(match.venue) : mapsUrl(match.venue)} target="_blank" rel="noopener">
        <Icon name="pin" size={14} />
        <span class="ellipsis">{match.venue}</span>
      </a>
    {:else}
      <span class="venue muted"><Icon name="pin" size={14} /> Pabellón por confirmar</span>
    {/if}
    <WeatherChip {match} compact />
  </footer>
</article>

<style>
  .upcoming {
    position: relative;
    overflow: hidden;
    margin-top: 10px;
    padding: 12px 14px 12px 18px;
    border-radius: var(--radius);
    border: 1px solid color-mix(in srgb, var(--brand) 25%, var(--line));
    background:
      radial-gradient(120% 100% at 100% 0%, rgba(49, 169, 67, 0.16), transparent 60%),
      linear-gradient(160deg, #eef8f0, var(--surface) 70%);
    box-shadow: var(--shadow);
    display: grid;
    gap: 10px;
  }
  /* Franja verde del club a la izquierda */
  .upcoming::before {
    content: '';
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 5px;
    background: linear-gradient(180deg, #3bbf50, #1f7f30);
  }
  @media (prefers-color-scheme: dark) {
    .upcoming {
      background:
        radial-gradient(120% 100% at 100% 0%, rgba(49, 169, 67, 0.22), transparent 60%),
        linear-gradient(160deg, #15301d, var(--surface) 70%);
    }
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
  header {
    display: flex;
    justify-content: space-between;
    font-size: 11.5px;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  .label {
    color: var(--brand-strong);
  }
  @media (prefers-color-scheme: dark) {
    .label {
      color: #7fe08f;
    }
  }
  .round {
    color: var(--muted);
  }
  .teams {
    display: grid;
    grid-template-columns: 1fr auto 1fr;
    align-items: center;
    gap: 8px;
  }
  .team {
    display: grid;
    justify-items: center;
    gap: 6px;
    min-width: 0;
    text-align: center;
  }
  .name {
    max-width: 100%;
    font-size: 13.5px;
    font-weight: 600;
    line-height: 1.2;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .team.ours .name {
    font-weight: 800;
  }
  .when {
    display: grid;
    justify-items: center;
    padding: 0 4px;
  }
  .day {
    font-size: 12.5px;
    font-weight: 700;
    color: var(--muted);
    white-space: nowrap;
  }
  .time {
    font-size: 24px;
    font-weight: 850;
    font-variant-numeric: tabular-nums;
    color: var(--brand-strong);
    line-height: 1.1;
  }
  @media (prefers-color-scheme: dark) {
    .time {
      color: #7fe08f;
    }
  }
  .time.vs {
    color: var(--muted);
  }
  footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    min-width: 0;
    padding-top: 8px;
    border-top: 1px solid color-mix(in srgb, var(--brand) 15%, var(--line));
  }
  .venue {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 4px;
    min-width: 0;
    font-size: 13px;
    color: var(--muted);
    text-decoration: none;
  }
  .venue :global(svg) {
    flex: none;
  }
</style>
