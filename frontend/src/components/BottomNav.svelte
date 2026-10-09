<script>
  import Icon from './Icon.svelte';

  let { active } = $props();

  const items = [
    { id: 'home', href: '#/', icon: 'home', label: 'Inicio' },
    { id: 'categories', href: '#/categorias', icon: 'trophy', label: 'Categorías' },
    { id: 'club', href: '#/club', icon: 'club', label: 'Club' },
  ];
  const index = $derived(Math.max(0, items.findIndex((i) => i.id === active)));
</script>

<nav class="nav" aria-label="Navegación principal">
  <div class="inner" style="--i:{index}; --n:{items.length}">
    <span class="indicator" class:hidden={!items.some((i) => i.id === active)}></span>
    {#each items as item}
      <a href={item.href} class:active={item.id === active} aria-current={item.id === active ? 'page' : undefined}>
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
    max-width: 420px;
    margin: 0 auto;
    height: var(--nav-h);
    display: grid;
    grid-template-columns: repeat(var(--n), 1fr);
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
    left: 6px;
    width: calc((100% - 12px) / var(--n));
    border-radius: 16px;
    background: var(--brand-soft);
    transform: translateX(calc(var(--i) * 100%));
    transition: transform 0.45s var(--spring), opacity 0.2s;
  }
  .indicator.hidden {
    opacity: 0;
  }
  a {
    position: relative;
    display: grid;
    place-items: center;
    align-content: center;
    gap: 2px;
    color: var(--muted);
    text-decoration: none;
    font-size: 11.5px;
    font-weight: 650;
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
</style>
