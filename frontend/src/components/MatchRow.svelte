<script>
  import Icon from './Icon.svelte';
  import TeamBadge from './TeamBadge.svelte';
  import { formatWhen, isOursName, liveMode, liveText, mapsUrl, ourOutcome, partialsText, roundLabel, scoreOf, shortTeam } from '../lib/format.js';
  import { go } from '../lib/router.js';
  import { matchText } from '../lib/share.js';
  import { openShare } from '../lib/shareSheet.js';
  import { dataFromMatch } from '../lib/shareData.js';

  let { match, category, showRound = false } = $props();
  const outcome = $derived(ourOutcome(match, isOursName));
  const score = $derived(scoreOf(match));
  const homeWon = $derived(score && score.home > score.away);
  const awayWon = $derived(score && score.away > score.home);
  const live = $derived(score ? null : liveMode(match.live));
</script>

{#if match.is_bye}
  <div class="row bye">
    <TeamBadge name={match.home} logo={match.home_logo} size={28} />
    <span class="ellipsis"><b>{shortTeam(match.home)}</b> descansa</span>
  </div>
{:else}
  <article class="row" class:ours={match.is_ours} class:win={outcome === true} class:loss={outcome === false}>
    {#if showRound}<div class="round">{roundLabel(match)}</div>{/if}
    <div class="line">
      <div class="teams">
        <div class="team" class:won={homeWon}>
          <TeamBadge name={match.home} logo={match.home_logo} size={26} />
          <span class="ellipsis">{shortTeam(match.home)}</span>
          {#if score}<b class="sets">{score.home}</b>{/if}
        </div>
        <div class="team" class:won={awayWon}>
          <TeamBadge name={match.away} logo={match.away_logo} size={26} />
          <span class="ellipsis">{shortTeam(match.away)}</span>
          {#if score}<b class="sets">{score.away}</b>{/if}
        </div>
      </div>
      {#if match.is_ours}
        <button class="share" onclick={() => openShare(dataFromMatch(match, category), matchText(category, match))} aria-label="Compartir">
          <Icon name="share" size={17} />
        </button>
      {/if}
    </div>
    <div class="meta">
      {#if score}
        {#if score.provisional}
          <span class="pill prov" title="Anotado por {score.by}">Provisional</span>
        {/if}
        {#if outcome !== null}
          <span class="pill" class:w={outcome} class:l={!outcome}>{outcome ? 'Victoria' : 'Derrota'}</span>
        {/if}
        {#if score.partials.length}<span class="partials">{partialsText(score)}</span>{/if}
        {#if match.cheers?.total}<span class="cheers">💚 {match.cheers.total} ánimos</span>{/if}
        {#if score.provisional}
          <span class="prov-note">Pendiente de confirmar por {match.tournament ? 'la organización' : 'la federación'}{score.early ? ' · terminado antes de tiempo' : ''}</span>
        {/if}
      {:else}
        {#if live}
          <button class="pill live" class:on={live === 'live'} onclick={() => go(`/directo/${match.live.id}`)}>
            <i aria-hidden="true"></i> {live === 'live' ? 'En directo' : 'Final'} · {liveText(match.live)}
          </button>
        {/if}
        {#if match.round_shift && !showRound}<span class="pill shift">{match.round_shift === 'adelantada' ? 'Adelantado' : 'Aplazado'}</span>{/if}
        <span class="when"><Icon name="clock" size={14} /> {formatWhen(match.starts_at)}</span>
        {#if match.schedule_override}<span class="club-note">Horario confirmado por el club</span>{/if}
        {#if match.venue}
          <a class="venue" href={mapsUrl(match.venue)} target="_blank" rel="noopener">
            <Icon name="pin" size={14} />
            <span>{match.venue}</span>
          </a>
        {/if}
      {/if}
    </div>
  </article>
{/if}

<style>
  .row {
    min-width: 0; /* elemento de rejilla: que no se estire con textos largos */
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
    align-items: flex-start;
    min-width: 0;
    color: var(--muted);
    text-decoration: none;
  }
  .venue :global(svg) {
    flex: none;
    margin-top: 1px;
  }
  .venue span {
    min-width: 0;
    overflow-wrap: anywhere; /* direcciones largas: pasan a la línea siguiente */
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
  .cheers {
    font-weight: 650;
    color: var(--brand-strong);
  }
  .pill.prov {
    background: rgba(242, 165, 22, 0.16);
    color: #a86a00;
  }
  @media (prefers-color-scheme: dark) {
    .pill.prov {
      color: #f5b94a;
    }
  }
  .pill.live {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    background: var(--brand-soft);
    color: var(--brand-strong);
    font-variant-numeric: tabular-nums;
  }
  .pill.live i {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: currentColor;
  }
  .pill.live.on {
    background: rgba(229, 72, 77, 0.12);
    color: var(--danger);
  }
  .pill.live.on i {
    animation: blink 1s infinite;
  }
  @keyframes blink {
    50% {
      opacity: 0.25;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .pill.live.on i {
      animation: none;
    }
  }
  .pill.shift {
    background: rgba(242, 165, 22, 0.16);
    color: #a86a00;
  }
  @media (prefers-color-scheme: dark) {
    .pill.shift {
      color: #f5b94a;
    }
  }
  .club-note {
    font-size: 12px;
    font-weight: 650;
    color: var(--brand-strong);
  }
  .prov-note {
    flex-basis: 100%;
    font-size: 12px;
    font-style: italic;
  }
</style>
