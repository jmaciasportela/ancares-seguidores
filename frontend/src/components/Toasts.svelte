<script>
  import { flip } from 'svelte/animate';
  import Icon from './Icon.svelte';
  import { toasts } from '../lib/toast.js';
  import { flipOpts, fly } from '../lib/motion.js';
</script>

<div class="toasts" aria-live="polite">
  {#each $toasts as t (t.id)}
    <div class="toast {t.kind}" animate:flip={flipOpts} transition:fly={{ y: -20 }}>
      <Icon name={t.kind === 'error' ? 'info' : 'check'} size={18} />
      <span>{t.message}</span>
    </div>
  {/each}
</div>

<style>
  .toasts {
    position: fixed;
    top: calc(var(--safe-top) + 12px);
    left: 12px;
    right: 12px;
    z-index: 60;
    display: grid;
    justify-items: center;
    gap: 8px;
    pointer-events: none;
  }
  .toast {
    display: flex;
    align-items: center;
    gap: 10px;
    max-width: 420px;
    padding: 12px 16px;
    border-radius: 14px;
    background: #13241a;
    color: #fff;
    font-size: 14.5px;
    font-weight: 600;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.25);
  }
  .toast.ok :global(svg) {
    color: #7fe08f;
  }
  .toast.error {
    background: #4a1416;
  }
</style>
