<script>
  import { tick } from 'svelte';
  import Icon from '../components/Icon.svelte';
  import MatchRow from '../components/MatchRow.svelte';
  import StandingsTable from '../components/StandingsTable.svelte';
  import { resource } from '../lib/api.js';
  import { formatDay, timeAgo } from '../lib/format.js';
  import { fly, reduced } from '../lib/motion.js';
  import { back, go, route } from '../lib/router.js';

  let { slug } = $props();

  const TABS = [
    { id: 'clasificacion', label: 'Clasificación' },
    { id: 'calendario', label: 'Calendario' },
    { id: 'resultados', label: 'Resultados' },
  ];

  const res = $derived(resource(`/api/categories/${slug}`));
  const data = $derived($res.data);
  const tab = $derived(TABS.some((t) => t.id === $route.query.get('t')) ? $route.query.get('t') : 'clasificacion');
  const tabIndex = $derived(TABS.findIndex((t) => t.id === tab));
  let direction = $state(1);
  let onlyOurs = $state(true);

  function setTab(id) {
    const next = TABS.findIndex((t) => t.id === id);
    direction = next > tabIndex ? 1 : -1;
    go(`/c/${slug}?t=${id}`, { replace: true });
  }

  // Deslizar a izquierda/derecha para cambiar de pestaña
  function swipe(node) {
    let touch = null;
    const start = (e) => {
      const t = e.touches[0];
      touch = { x: t.clientX, y: t.clientY, time: Date.now() };
    };
    const end = (e) => {
      if (!touch) return;
      const t = e.changedTouches[0];
      const dx = t.clientX - touch.x;
      const dy = t.clientY - touch.y;
      const fast = Date.now() - touch.time < 600;
      touch = null;
      if (fast && Math.abs(dx) > 70 && Math.abs(dx) > Math.abs(dy) * 1.8) {
        const next = tabIndex + (dx < 0 ? 1 : -1);
        if (next >= 0 && next < TABS.length) setTab(TABS[next].id);
      }
    };
    node.addEventListener('touchstart', start, { passive: true });
    node.addEventListener('touchend', end, { passive: true });
    return {
      destroy() {
        node.removeEventListener('touchstart', start);
        node.removeEventListener('touchend', end);
      },
    };
  }

  const matches = $derived(data?.matches || []);
  const visible = $derived(onlyOurs ? matches.filter((m) => m.is_ours) : matches);
  const rounds = $derived.by(() => {
    const map = new Map();
    for (const m of visible) {
      if (!map.has(m.round_no)) map.set(m.round_no, { no: m.round_no, name: m.round_name, matches: [] });
      map.get(m.round_no).matches.push(m);
    }
    for (const r of map.values()) {
      const dates = r.matches.map((m) => m.starts_at).filter(Boolean).sort();
      r.date = dates[0] || null;
    }
    return [...map.values()].sort((a, b) => a.no - b.no);
  });
  const nextRound = $derived.by(() => {
    const now = Date.now() - 3 * 3600e3;
    const pending = matches.filter((m) => !m.is_bye && !m.played);
    const upcoming = pending.find((m) => m.starts_at && new Date(m.starts_at).getTime() >= now);
    return (upcoming || pending[0])?.round_no ?? null;
  });
  const played = $derived(
    visible.filter((m) => m.played).sort((a, b) => b.round_no - a.round_no || (b.starts_at || '').localeCompare(a.starts_at || '')),
  );

  // Al abrir el calendario, saltar a la próxima jornada
  $effect(() => {
    if (tab !== 'calendario' || nextRound === null) return;
    const roundNo = nextRound;
    tick().then(() =>
      setTimeout(() => {
        document.getElementById(`round-${roundNo}`)?.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'start' });
      }, 250),
    );
  });
</script>

<div class="top">
  <div class="bar">
    <button class="back" onclick={() => back('/categorias')} aria-label="Volver"><Icon name="back" size={24} /></button>
    <div class="name">
      <h1 class="ellipsis">{data?.name || 'Cargando…'}</h1>
      {#if data?.updated_at}<span class="muted">Actualizado {timeAgo(data.updated_at)}</span>{/if}
    </div>
    {#if data?.our_position}
      <span class="pos">{data.our_position}º</span>
    {/if}
  </div>
  <div class="tabs" role="tablist" style="--i:{tabIndex}">
    <span class="ind"></span>
    {#each TABS as t}
      <button role="tab" aria-selected={tab === t.id} class:active={tab === t.id} onclick={() => setTab(t.id)}>{t.label}</button>
    {/each}
  </div>
</div>

<div class="page content" use:swipe>
  {#if !data && $res.loading}
    <div class="skeleton" style="height:420px"></div>
  {:else if !data && $res.error}
    <div class="card empty">
      <p>{$res.error.status === 404 ? 'Esta categoría no existe.' : 'No se pudieron cargar los datos.'}</p>
      <button class="btn" onclick={() => res.refresh()}>Reintentar</button>
    </div>
  {:else if data}
    {#key tab}
      <div class="pane" in:fly={{ x: 40 * direction, y: 0, duration: 320 }}>
        {#if tab === 'clasificacion'}
          {#if data.standings.length}
            <StandingsTable standings={data.standings} />
            <p class="legend muted">Pts: puntos · PJ: jugados · G: ganados · P: perdidos · Sets: a favor - en contra</p>
          {:else}
            <div class="card empty">Aún no hay clasificación.</div>
          {/if}
        {:else}
          <label class="toggle">
            <input type="checkbox" bind:checked={onlyOurs} />
            <span class="sw"></span>
            Solo partidos de Ancares
          </label>

          {#if tab === 'calendario'}
            {#each rounds as r (r.no)}
              <section class="round" id="round-{r.no}">
                <h2>
                  <span>{r.name}</span>
                  {#if r.no === nextRound}<span class="chip brand">Próxima</span>{/if}
                  {#if r.date}<span class="date muted">{formatDay(r.date)}</span>{/if}
                </h2>
                <div class="matches">
                  {#each r.matches as m (m.id)}
                    <MatchRow match={m} category={data.name} />
                  {/each}
                </div>
              </section>
            {:else}
              <div class="card empty">No hay partidos en el calendario.</div>
            {/each}
          {:else}
            <div class="matches">
              {#each played as m, i (m.id)}
                <div in:fly={{ y: 12, delay: Math.min(i * 40, 400) }}>
                  <MatchRow match={m} category={data.name} showRound />
                </div>
              {:else}
                <div class="card empty">
                  <Icon name="ball" size={36} />
                  <p>Todavía no se ha jugado ningún partido.<br />¡Ánimo a todas! 💚</p>
                </div>
              {/each}
            </div>
          {/if}
        {/if}
      </div>
    {/key}
  {/if}
</div>

<style>
  .top {
    position: sticky;
    top: 0;
    z-index: 10;
    padding: calc(var(--safe-top) + 8px) 12px 10px;
    background: color-mix(in srgb, var(--bg) 85%, transparent);
    backdrop-filter: saturate(1.5) blur(16px);
    -webkit-backdrop-filter: saturate(1.5) blur(16px);
    border-bottom: 1px solid var(--line);
  }
  .bar,
  .tabs {
    max-width: 616px;
    margin: 0 auto;
  }
  .bar {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .back {
    width: 40px;
    height: 40px;
    display: grid;
    place-items: center;
    border-radius: 50%;
    color: var(--text);
  }
  .back:active {
    background: var(--surface-2);
  }
  .name {
    flex: 1;
    min-width: 0;
    display: grid;
  }
  .name h1 {
    font-size: 19px;
    font-weight: 800;
  }
  .name span {
    font-size: 12.5px;
  }
  .pos {
    flex: none;
    padding: 6px 12px;
    border-radius: 12px;
    background: var(--brand);
    color: #fff;
    font-weight: 850;
    font-size: 16px;
  }
  .tabs {
    position: relative;
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    margin-top: 10px;
    padding: 4px;
    border-radius: 14px;
    background: var(--surface-2);
  }
  .ind {
    position: absolute;
    top: 4px;
    bottom: 4px;
    left: 4px;
    width: calc((100% - 8px) / 3);
    border-radius: 10px;
    background: var(--surface);
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12);
    transform: translateX(calc(var(--i) * 100%));
    transition: transform 0.4s var(--spring);
  }
  .tabs button {
    position: relative;
    min-height: 36px;
    font-size: 14px;
    font-weight: 650;
    color: var(--muted);
    transition: color 0.2s;
  }
  .tabs button.active {
    color: var(--text);
  }
  .content {
    min-height: 70vh;
    overflow-x: hidden;
  }
  .legend {
    font-size: 12px;
    text-align: center;
    margin-top: 12px;
  }
  .toggle {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 2px 2px 14px;
    font-size: 14.5px;
    font-weight: 600;
    cursor: pointer;
    user-select: none;
  }
  .toggle input {
    position: absolute;
    opacity: 0;
  }
  .sw {
    position: relative;
    width: 44px;
    height: 26px;
    border-radius: 13px;
    background: var(--line);
    transition: background 0.25s;
  }
  .sw::after {
    content: '';
    position: absolute;
    top: 3px;
    left: 3px;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: #fff;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.25);
    transition: transform 0.3s var(--spring);
  }
  .toggle input:checked + .sw {
    background: var(--brand);
  }
  .toggle input:checked + .sw::after {
    transform: translateX(18px);
  }
  .toggle input:focus-visible + .sw {
    outline: 2px solid var(--brand);
    outline-offset: 2px;
  }
  .round {
    scroll-margin-top: calc(var(--safe-top) + 130px);
    margin-bottom: 20px;
  }
  .round h2 {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 15px;
    font-weight: 800;
    margin: 0 2px 8px;
  }
  .round h2 .date {
    margin-left: auto;
    font-size: 13px;
    font-weight: 600;
  }
  .matches {
    display: grid;
    gap: 8px;
  }
  .empty {
    display: grid;
    justify-items: center;
    gap: 10px;
    padding: 32px 20px;
    text-align: center;
    color: var(--muted);
  }
  .empty p {
    margin: 0;
  }
</style>
