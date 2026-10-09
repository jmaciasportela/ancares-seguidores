<script>
  import { initials, isOursName, teamHue } from '../lib/format.js';

  let { name, logo = null, size = 36 } = $props();
  const ours = $derived(isOursName(name));
  const hue = $derived(teamHue(name));
  let failed = $state(false);
  $effect(() => {
    logo; // si cambia el logo, volver a intentarlo
    failed = false;
  });
</script>

{#if ours}
  <img class="badge ours" src="/logo-256.webp" alt="" width={size} height={size} style="width:{size}px;height:{size}px" />
{:else if logo && !failed}
  <img
    class="badge logo"
    src={logo}
    alt=""
    width={size}
    height={size}
    loading="lazy"
    decoding="async"
    style="width:{size}px;height:{size}px;padding:{Math.round(size * 0.08)}px"
    onerror={() => (failed = true)}
  />
{:else}
  <span
    class="badge initials"
    style="width:{size}px;height:{size}px;font-size:{size * 0.36}px;--h:{hue}"
    aria-hidden="true">{initials(name)}</span
  >
{/if}

<style>
  .badge {
    flex: none;
    border-radius: 50%;
    display: grid;
    place-items: center;
  }
  img.ours {
    box-shadow: 0 0 0 2px var(--brand);
    background: #fff;
  }
  img.logo {
    /* Los escudos vienen recortados en un cuadrado transparente */
    object-fit: contain;
    background: #fff;
    box-shadow: 0 0 0 1px var(--line);
  }
  .initials {
    font-weight: 800;
    letter-spacing: 0.02em;
    color: hsl(var(--h) 45% 30%);
    background: hsl(var(--h) 60% 90%);
  }
  @media (prefers-color-scheme: dark) {
    .initials {
      color: hsl(var(--h) 60% 82%);
      background: hsl(var(--h) 30% 22%);
    }
  }
</style>
