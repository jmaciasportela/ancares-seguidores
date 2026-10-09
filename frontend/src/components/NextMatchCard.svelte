<script>
  import Countdown from './Countdown.svelte';
  import Icon from './Icon.svelte';
  import TeamBadge from './TeamBadge.svelte';
  import { formatDay, formatTime, mapsUrl, shortTeam } from '../lib/format.js';
  import { shareMatch } from '../lib/share.js';

  let { match, category } = $props();
</script>

<article class="next">
  <header>
    <span class="label">Próximo partido</span>
    <span class="round">{match.round_name}</span>
  </header>

  <div class="teams">
    <div class="team">
      <TeamBadge name={match.home} size={52} />
      <span class="name">{shortTeam(match.home)}</span>
    </div>
    <div class="vs">
      <span class="time">{match.starts_at ? formatTime(match.starts_at) : 'VS'}</span>
      <span class="day">{formatDay(match.starts_at)}</span>
    </div>
    <div class="team">
      <TeamBadge name={match.away} size={52} />
      <span class="name">{shortTeam(match.away)}</span>
    </div>
  </div>

  {#if match.starts_at}
    <div class="countdown"><Countdown iso={match.starts_at} /></div>
  {/if}

  <footer>
    {#if match.venue}
      <a class="venue" href={mapsUrl(match.venue)} target="_blank" rel="noopener">
        <Icon name="pin" size={16} />
        <span class="ellipsis">{match.venue}</span>
      </a>
    {:else}
      <span class="venue"><Icon name="pin" size={16} /> Pabellón por confirmar</span>
    {/if}
    <button class="share" onclick={() => shareMatch(category, match)} aria-label="Compartir partido">
      <Icon name="share" size={18} />
    </button>
  </footer>
</article>

<style>
  .next {
    position: relative;
    overflow: hidden;
    border-radius: var(--radius);
    padding: 16px;
    color: #fff;
    background:
      radial-gradient(120% 90% at 100% 0%, rgba(49, 169, 67, 0.55), transparent 60%),
      linear-gradient(160deg, #143a1f, #0b1a10);
    box-shadow: 0 10px 30px rgba(11, 26, 16, 0.35);
  }
  .next::after {
    /* balón decorativo */
    content: '';
    position: absolute;
    right: -40px;
    bottom: -40px;
    width: 160px;
    height: 160px;
    border-radius: 50%;
    border: 18px solid rgba(255, 255, 255, 0.04);
    pointer-events: none;
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  .label {
    color: #8ee39c;
  }
  .round {
    opacity: 0.7;
  }
  .teams {
    display: grid;
    grid-template-columns: 1fr auto 1fr;
    align-items: start;
    gap: 8px;
    margin: 16px 0 14px;
  }
  .team {
    display: grid;
    justify-items: center;
    gap: 8px;
    text-align: center;
    min-width: 0;
  }
  .name {
    font-weight: 700;
    font-size: 14.5px;
    line-height: 1.2;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .vs {
    display: grid;
    justify-items: center;
    padding-top: 8px;
  }
  .time {
    font-size: 26px;
    font-weight: 800;
    font-variant-numeric: tabular-nums;
  }
  .day {
    font-size: 13px;
    opacity: 0.8;
  }
  .countdown {
    display: flex;
    justify-content: center;
    margin-bottom: 14px;
  }
  footer {
    display: flex;
    align-items: center;
    gap: 10px;
    padding-top: 12px;
    border-top: 1px solid rgba(255, 255, 255, 0.1);
  }
  .venue {
    flex: 1;
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 6px;
    color: rgba(255, 255, 255, 0.85);
    font-size: 14px;
    text-decoration: none;
  }
  .share {
    flex: none;
    width: 40px;
    height: 40px;
    border-radius: 50%;
    display: grid;
    place-items: center;
    color: #fff;
    background: rgba(255, 255, 255, 0.12);
    transition: transform 0.15s;
  }
  .share:active {
    transform: scale(0.9);
  }
</style>
