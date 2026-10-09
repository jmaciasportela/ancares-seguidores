<script>
  import Icon from './Icon.svelte';
  import TeamBadge from './TeamBadge.svelte';
  import { formatWhen, isOursName, mapsUrl, ourOutcome, partialsText, shortTeam } from '../lib/format.js';
  import { shareMatch } from '../lib/share.js';

  let { match, category, showRound = false } = $props();
  const outcome = $derived(ourOutcome(match, isOursName));
  const homeWon = $derived(match.played && match.home_sets > match.away_sets);
  const awayWon = $derived(match.played && match.away_sets > match.home_sets);
</script>

{#if match.is_bye}
  <div class="row bye">
    <TeamBadge name={match.home} size={28} />
    <span class="ellipsis"><b>{shortTeam(match.home)}</b> descansa</span>
  </div>
{:else}
  <article class="row" class:ours={match.is_ours} class:win={outcome === true} class:loss={outcome === false}>
    {#if showRound}<div class="round">{match.round_name}</div>{/if}
    <div class="line">
      <div class="teams">
        <div class="team" class:won={homeWon}>
          <TeamBadge name={match.home} size={26} />
          <span class="ellipsis">{shortTeam(match.home)}</span>
          {#if match.played}<b class="sets">{match.home_sets}</b>{/if}
        </div>
        <div class="team" class:won={awayWon}>
          <TeamBadge name={match.away} size={26} />
          <span class="ellipsis">{shortTeam(match.away)}</span>
          {#if match.played}<b class="sets">{match.away_sets}</b>{/if}
        </div>
      </div>
      {#if match.is_ours}
        <button class="share" onclick={() => shareMatch(category, match)} aria-label="Compartir">
          <Icon name="share" size={17} />
        </button>
      {/if}
    </div>
    <div class="meta">
      {#if match.played}
        {#if outcome !== null}
          <span class="pill" class:w={outcome} class:l={!outcome}>{outcome ? 'Victoria' : 'Derrota'}</span>
        {/if}
        {#if match.partials?.length}<span class="partials">{partialsText(match)}</span>{/if}
      {:else}
        <span class="when"><Icon name="clock" size={14} /> {formatWhen(match.starts_at)}</span>
        {#if match.venue}
          <a class="venue ellipsis" href={mapsUrl(match.venue)} target="_blank" rel="noopener">
            <Icon name="pin" size={14} />
            {match.venue}
          </a>
        {/if}
      {/if}
    </div>
  </article>
{/if}

<style>
  .row {
    padding: 12px 14px;
    border-radius: var(--radius-sm);
    background: var(--surface);
    border: 1px solid var(--line);
    display: grid;
    gap: 8px;
  }
  .row.ours {
    border-color: color-mix(in srgb, var(--brand) 45%, var(--line));
    box-shadow: inset 3px 0 0 var(--brand);
  }
  .row.ours.loss {
    box-shadow: inset 3px 0 0 var(--danger);
  }
  .bye {
    display: flex;
    align-items: center;
    gap: 10px;
    color: var(--muted);
    font-size: 14px;
    background: transparent;
    border-style: dashed;
  }
  .round {
    font-size: 12px;
    font-weight: 700;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .line {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .teams {
    flex: 1;
    min-width: 0;
    display: grid;
    gap: 6px;
  }
  .team {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 15px;
    min-width: 0;
  }
  .team span {
    flex: 1;
    min-width: 0;
  }
  .team.won {
    font-weight: 750;
  }
  .sets {
    font-size: 18px;
    font-variant-numeric: tabular-nums;
    min-width: 18px;
    text-align: right;
  }
  .team:not(.won) .sets {
    color: var(--muted);
    font-weight: 600;
  }
  .share {
    flex: none;
    width: 38px;
    height: 38px;
    border-radius: 50%;
    display: grid;
    place-items: center;
    background: var(--brand-soft);
    color: var(--brand-strong);
  }
  .meta {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px 12px;
    font-size: 13px;
    color: var(--muted);
  }
  .meta :global(svg) {
    vertical-align: -2px;
  }
  .when,
  .venue {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    max-width: 100%;
  }
  .venue {
    color: var(--muted);
    text-decoration: none;
  }
  .pill {
    padding: 2px 8px;
    border-radius: 999px;
    font-weight: 700;
    font-size: 12px;
  }
  .pill.w {
    background: var(--brand-soft);
    color: var(--brand-strong);
  }
  .pill.l {
    background: rgba(229, 72, 77, 0.12);
    color: var(--danger);
  }
  .partials {
    font-variant-numeric: tabular-nums;
  }
</style>
