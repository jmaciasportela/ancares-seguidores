<script>
  import { onMount } from 'svelte';
  import BottomNav from './components/BottomNav.svelte';
  import Toasts from './components/Toasts.svelte';
  import { resource } from './lib/api.js';
  import { fade, reduced } from './lib/motion.js';
  import { route } from './lib/router.js';
  import Admin from './routes/admin/Admin.svelte';
  import Categories from './routes/Categories.svelte';
  import Category from './routes/Category.svelte';
  import Club from './routes/Club.svelte';
  import Home from './routes/Home.svelte';

  const view = $derived.by(() => {
    const [first, second] = $route.parts;
    if (!first) return { page: 'home', nav: 'home' };
    if (first === 'categorias') return { page: 'categories', nav: 'categories' };
    if (first === 'c' && second) return { page: 'category', nav: 'categories', slug: second };
    if (first === 'club') return { page: 'club', nav: 'club' };
    if (first === 'admin') return { page: 'admin', nav: null };
    return { page: 'home', nav: 'home' };
  });
  // La clave de la transición ignora la pestaña (?t=) para no recargar la página entera
  const pageKey = $derived(view.page + (view.slug || ''));

  // Splash: se muestra un mínimo en el primer arranque de la sesión y se retira
  // en cuanto hay datos (cacheados o frescos) o, como mucho, a los 1,5 s.
  onMount(() => {
    const boot = document.getElementById('boot');
    if (!boot) return;
    let first = true;
    try {
      first = !sessionStorage.getItem('ancares:booted');
      sessionStorage.setItem('ancares:booted', '1');
    } catch {
      /* modo privado */
    }
    const minMs = first && !reduced ? 900 : 0;
    const started = performance.now();
    const hide = () => {
      const wait = Math.max(0, minMs - (performance.now() - started));
      setTimeout(() => {
        boot.classList.add('hide');
        setTimeout(() => boot.remove(), 500);
      }, wait);
    };
    const home = resource('/api/home');
    let done = false;
    const unsub = home.subscribe((s) => {
      if (!done && (s.data || !s.loading)) {
        done = true;
        hide();
      }
    });
    const max = setTimeout(() => !done && ((done = true), hide()), 1500);
    return () => {
      unsub();
      clearTimeout(max);
    };
  });

  $effect(() => {
    // Al cambiar de página, volver arriba
    pageKey;
    window.scrollTo({ top: 0 });
  });
</script>

<Toasts />

{#key pageKey}
  <main in:fade={{ duration: 200 }}>
    {#if view.page === 'home'}
      <Home />
    {:else if view.page === 'categories'}
      <Categories />
    {:else if view.page === 'category'}
      <Category slug={view.slug} />
    {:else if view.page === 'club'}
      <Club />
    {:else if view.page === 'admin'}
      <Admin />
    {/if}
  </main>
{/key}

{#if view.nav}
  <BottomNav active={view.nav} />
{/if}
