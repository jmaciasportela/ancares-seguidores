<script>
  import Icon from '../components/Icon.svelte';
  import { resource } from '../lib/api.js';
  import { formatWhen } from '../lib/format.js';
  import { fly } from '../lib/motion.js';

  const home = resource('/api/home');
  const cats = $derived($home.data?.categories || []);
</script>

<div class="page">
  <h1 class="title" in:fly={{ y: -10 }}>Categorías</h1>

  {#if !$home.data && $home.loading}
    {#each [1, 2, 3] as _}
      <div class="skeleton" style="height:84px;margin-bottom:12px"></div>
    {/each}
  {/if}

  <div class="list">
    {#each cats as cat, i (cat.id)}
      <a class="item card" href="#/c/{cat.slug}" in:fly={{ y: 20, delay: i * 60 }}>
        <div class="pos" class:none={!cat.our_position}>
          {#if cat.our_position}
            <b>{cat.our_position}º</b><span>de {cat.teams}</span>
          {:else}
            <Icon name="ball" size={22} />
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
    {/each}
  </div>
</div>

<style>
  .title {
    font-size: 28px;
    font-weight: 850;
    padding-top: calc(var(--safe-top) + 8px);
    margin-bottom: 18px;
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
  .info span {
    font-size: 13.5px;
  }
</style>
