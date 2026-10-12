<script>
  import Icon from '../components/Icon.svelte';
  import { resource } from '../lib/api.js';
  import { formatWhen } from '../lib/format.js';
  import { fly } from '../lib/motion.js';

  const home = resource('/api/home');
  const cats = $derived($home.data?.categories || []);
  // La liga es lo principal: siempre arriba; los torneos, en su propio bloque
  const leagues = $derived(cats.filter((c) => c.kind !== 'tournament'));
  const tournaments = $derived(cats.filter((c) => c.kind === 'tournament'));
</script>

{#snippet item(cat, i)}
  <a class="item card" href="#/c/{cat.slug}" in:fly={{ y: 20, delay: i * 60 }}>
    <div class="pos" class:none={!cat.our_position} class:tour={cat.kind === 'tournament'}>
      {#if cat.our_position}
        <b>{cat.our_position}º</b><span>de {cat.teams}</span>
      {:else}
        <Icon name={cat.kind === 'tournament' ? 'trophy' : 'ball'} size={22} />
      {/if}
    </div>
    <div class="info">
      <h2 class="ellipsis">{cat.name}</h2>
      <span class="muted ellipsis">
        {#if cat.next_match}
          Próximo: {formatWhen(cat.next_match.starts_at)}
        {:else if cat.our_points !== null}
          {cat.our_points} puntos
        {:else}
          Sin datos todavía
        {/if}
      </span>
    </div>
    <Icon name="chevron" size={20} />
  </a>
{/snippet}

<div class="page">
  <h1 class="title" in:fly={{ y: -10 }}>Competiciones</h1>

  {#if !$home.data && $home.loading}
    {#each [1, 2, 3] as _}
      <div class="skeleton" style="height:84px;margin-bottom:12px"></div>
    {/each}
  {/if}

  {#if leagues.length}
    {#if tournaments.length}<h2 class="section-title">Ligas</h2>{/if}
    <div class="list">
      {#each leagues as cat, i (cat.id)}{@render item(cat, i)}{/each}
    </div>
  {/if}

  {#if tournaments.length}
    <h2 class="section-title">Torneos</h2>
    <div class="list">
      {#each tournaments as cat, i (cat.id)}{@render item(cat, leagues.length + i)}{/each}
    </div>
  {/if}
</div>

<style>
  .title {
    font-size: 28px;
    font-weight: 850;
    padding-top: calc(var(--safe-top) + 8px);
    margin-bottom: 6px;
  }
  .section-title:first-of-type {
    margin-top: 12px;
  }
  .list {
    display: grid;
    gap: 12px;
  }
  .item {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 14px;
    color: var(--text);
    text-decoration: none;
    transition: transform 0.15s var(--ease-out);
  }
  .item:active {
    transform: scale(0.98);
  }
  .item > :global(svg) {
    color: var(--muted);
    flex: none;
  }
  .pos {
    flex: none;
    width: 56px;
    height: 56px;
    border-radius: 16px;
    display: grid;
    place-items: center;
    align-content: center;
    background: var(--brand);
    color: #fff;
    line-height: 1;
  }
  .pos b {
    font-size: 21px;
    font-weight: 850;
  }
  .pos span {
    font-size: 11px;
    opacity: 0.85;
    margin-top: 2px;
  }
  .pos.none {
    background: var(--surface-2);
    color: var(--muted);
  }
  .info {
    flex: 1;
    min-width: 0;
    display: grid;
    gap: 2px;
  }
  h2 {
    font-size: 17px;
    font-weight: 750;
  }
  .pos.tour {
    background: rgba(49, 120, 198, 0.14);
    color: #2563b0;
  }
  @media (prefers-color-scheme: dark) {
    .pos.tour {
      color: #7fb2ef;
    }
  }
  .info span {
    font-size: 13.5px;
  }
</style>
