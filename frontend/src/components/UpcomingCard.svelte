<script>
  import Icon from './Icon.svelte';
  import TeamBadge from './TeamBadge.svelte';
  import WeatherChip from './WeatherChip.svelte';
  import { formatDay, formatTime, isOursName, mapsUrl, shortTeam } from '../lib/format.js';

  /** Tarjeta compacta para el partido que va después del próximo. */
  let { match } = $props();
  const oursHome = $derived(isOursName(match.home));
  const rival = $derived(oursHome ? match.away : match.home);
  const rivalLogo = $derived(oursHome ? match.away_logo : match.home_logo);
</script>

<article class="upcoming card">
  <header>
    <span class="label">Siguiente partido</span>
    <span class="round">{match.round_name}</span>
  </header>
  <div class="body">
    <div class="teams">
      <TeamBadge name={match.home} logo={match.home_logo} size={34} />
      <span class="vs">vs</span>
      <TeamBadge name={match.away} logo={match.away_logo} size={34} />
    </div>
    <div class="info">
      <b class="ellipsis">{oursHome ? 'vs' : 'en casa de'} {shortTeam(rival)}</b>
      <span class="when">
        {formatDay(match.starts_at)}{#if match.starts_at}{' · '}{formatTime(match.starts_at)}{/if}
      </span>
    </div>
  </div>
  <div class="foot">
    {#if match.venue}
      <a class="venue" href={mapsUrl(match.venue)} target="_blank" rel="noopener">
        <Icon name="pin" size={14} />
        <span class="ellipsis">{match.venue}</span>
      </a>
    {/if}
    <WeatherChip {match} compact />
  </div>
</article>

<style>
  .upcoming {
    padding: 12px 14px;
    margin-top: 10px;
    display: grid;
    gap: 10px;
  }
  header {
    display: flex;
    justify-content: space-between;
    font-size: 11.5px;
    font-weight: 700;
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
  .body {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .teams {
    display: flex;
    align-items: center;
    gap: 6px;
    flex: none;
  }
  .vs {
    font-size: 11px;
    font-weight: 700;
    color: var(--muted);
  }
  .info {
    flex: 1;
    min-width: 0;
    display: grid;
  }
  .info b {
    font-size: 15.5px;
  }
  .when {
    font-size: 13.5px;
    color: var(--muted);
    font-weight: 600;
  }
  .foot {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    min-width: 0;
  }
  .foot:empty {
    display: none;
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
