<script>
  import Icon from '../components/Icon.svelte';
  import InstallBanner from '../components/InstallBanner.svelte';
  import MatchRow from '../components/MatchRow.svelte';
  import NextMatchCard from '../components/NextMatchCard.svelte';
  import { resource } from '../lib/api.js';
  import { timeAgo } from '../lib/format.js';
  import { fly } from '../lib/motion.js';

  const home = resource('/api/home');
  const cats = $derived($home.data?.categories || []);
</script>

<div class="page">
  <header class="hero" in:fly={{ y: -10 }}>
    <img src="/logo-256.webp" alt="Voleibol Ancares" width="56" height="56" />
    <div class="titles">
      <span class="hello">Familias de</span>
      <h1>Voleibol Ancares</h1>
    </div>
    <button
      class="refresh"
      class:spin={$home.loading}
      onclick={() => home.refresh()}
      aria-label="Actualizar datos"
      title="Actualizar"
    >
      <Icon name="refresh" size={20} />
    </button>
  </header>

  <p class="updated muted">
    {#if $home.error && !$home.data}
      Sin conexión y sin datos guardados todavía.
    {:else if $home.data?.updated_at}
      Datos de la federación · actualizados {timeAgo($home.data.updated_at)}
    {:else if !$home.loading}
      Aún no hay datos cargados.
    {/if}
  </p>

  <InstallBanner />

  {#if !$home.data && $home.loading}
    <div class="skeleton" style="height:260px"></div>
    <div class="skeleton" style="height:90px;margin-top:12px"></div>
  {:else if cats.length === 0 && !$home.loading}
    <div class="empty card" in:fly>
      <Icon name="ball" size={40} />
      <p>Todavía no hay categorías. ¡Vuelve pronto!</p>
    </div>
  {/if}

  {#each cats as cat, i (cat.id)}
    <section class="cat" in:fly={{ y: 24, delay: 80 + i * 90 }}>
      <a class="cat-head" href="#/c/{cat.slug}">
        <h2>{cat.name}</h2>
        {#if cat.our_position}
          <span class="chip brand">{cat.our_position}º · {cat.our_points} pts</span>
        {/if}
        <Icon name="chevron" size={18} />
      </a>

      {#if cat.next_match}
        <NextMatchCard match={cat.next_match} category={cat.name} />
      {:else}
        <div class="nomatch card muted">No hay próximos partidos programados.</div>
      {/if}

      {#if cat.last_result}
        <div class="last">
          <span class="section-title">Último resultado</span>
          <MatchRow match={cat.last_result} category={cat.name} showRound />
        </div>
      {/if}
    </section>
  {/each}
</div>

<style>
  .hero {
    display: flex;
    align-items: center;
    gap: 12px;
    padding-top: calc(var(--safe-top) + 4px);
  }
  .hero img {
    border-radius: 50%;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.15);
  }
  .titles {
    flex: 1;
    min-width: 0;
  }
  .hello {
    font-size: 13px;
    color: var(--muted);
    font-weight: 600;
  }
  h1 {
    font-size: 24px;
    font-weight: 850;
    letter-spacing: -0.01em;
  }
  .refresh {
    width: 42px;
    height: 42px;
    border-radius: 50%;
    display: grid;
    place-items: center;
    background: var(--surface);
    border: 1px solid var(--line);
    color: var(--muted);
  }
  .refresh.spin :global(svg) {
    animation: spin 0.9s linear infinite;
  }
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
  .updated {
    font-size: 13px;
    margin: 10px 2px 16px;
    min-height: 18px;
  }
  .cat {
    margin-bottom: 28px;
  }
  .cat-head {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 0 2px 10px;
    color: var(--text);
    text-decoration: none;
  }
  .cat-head h2 {
    flex: 1;
    font-size: 19px;
    font-weight: 800;
  }
  .cat-head :global(svg) {
    color: var(--muted);
  }
  .last .section-title {
    display: block;
    margin-top: 14px;
  }
  .nomatch {
    padding: 18px;
    text-align: center;
    font-size: 14px;
  }
  .empty {
    display: grid;
    justify-items: center;
    gap: 8px;
    padding: 36px 20px;
    color: var(--muted);
    text-align: center;
  }
</style>
