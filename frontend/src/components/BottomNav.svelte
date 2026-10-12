<script>
  import Icon from './Icon.svelte';

  let { active } = $props();

  const items = [
    { id: 'home', href: '#/', icon: 'home', label: 'Inicio' },
    { id: 'categories', href: '#/categorias', icon: 'trophy', label: 'Competiciones' },
    { id: 'marcador', href: '#/marcador', icon: 'score', label: 'Marcador' },
    { id: 'club', href: '#/club', icon: 'club', label: 'Club' },
  ];
  const index = $derived(items.findIndex((i) => i.id === active));

  // Cada pestaña ocupa según su texto («Club» necesita menos que «Competiciones»),
  // así que el marco verde se mide sobre la pestaña activa.
  let inner;
  let links = $state([]);
  let ind = $state({ left: 0, width: 0 });
  function measure() {
    const el = links[index];
    if (el) ind = { left: el.offsetLeft, width: el.offsetWidth };
  }
  $effect(() => {
    index;
    measure();
  });
  $effect(() => {
    if (!inner) return;
    const ro = new ResizeObserver(measure);
    ro.observe(inner);
    links.forEach((el) => el && ro.observe(el));
    return () => ro.disconnect();
  });
</script>

<nav class="nav" aria-label="Navegación principal">
  <div class="inner" bind:this={inner}>
    <span
      class="indicator"
      class:hidden={index < 0 || !ind.width}
      style="transform:translateX({ind.left}px);width:{ind.width}px"
    ></span>
    {#each items as item, i}
      <a
        bind:this={links[i]}
        href={item.href}
        class:active={item.id === active}
        aria-current={item.id === active ? 'page' : undefined}
      >
        <Icon name={item.icon} size={23} stroke={item.id === active ? 2.3 : 1.9} />
        <span>{item.label}</span>
      </a>
    {/each}
  </div>
</nav>

<style>
  .nav {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 20;
    padding: 0 12px calc(var(--safe-bottom) + 8px);
    pointer-events: none;
  }
  .inner {
    pointer-events: auto;
    position: relative;
    max-width: 460px;
    margin: 0 auto;
    height: var(--nav-h);
    display: flex;
    padding: 6px;
    border-radius: 22px;
    background: color-mix(in srgb, var(--surface) 82%, transparent);
    backdrop-filter: saturate(1.6) blur(18px);
    -webkit-backdrop-filter: saturate(1.6) blur(18px);
    border: 1px solid var(--line);
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.14);
  }
  .indicator {
    position: absolute;
    top: 6px;
    bottom: 6px;
    left: 0;
    border-radius: 16px;
    background: var(--brand-soft);
    transition: transform 0.45s var(--spring), width 0.45s var(--spring), opacity 0.2s;
  }
  .indicator.hidden {
    opacity: 0;
  }
  a {
    position: relative;
    /* El ancho base es el del texto; el sobrante se reparte a partes iguales */
    flex: 1 1 auto;
    min-width: 0;
    padding: 0 8px;
    display: grid;
    place-items: center;
    align-content: center;
    gap: 2px;
    color: var(--muted);
    text-decoration: none;
    font-size: 11.5px;
    font-weight: 650;
    white-space: nowrap;
    transition: color 0.2s;
  }
  a.active {
    color: var(--brand-strong);
  }
  @media (prefers-color-scheme: dark) {
    a.active {
      color: #7fe08f;
    }
  }
  a :global(svg) {
    transition: transform 0.35s var(--spring);
  }
  a.active :global(svg) {
    transform: translateY(-1px) scale(1.08);
  }
  /* Móviles muy estrechos: un poco menos de letra y de margen */
  @media (max-width: 350px) {
    a {
      padding: 0 5px;
      font-size: 10.5px;
    }
  }
</style>
