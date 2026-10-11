<script>
  import { fade, fly } from '../lib/motion.js';

  let { open = false, onClose = null, children } = $props();
</script>

{#if open}
  <div class="backdrop" transition:fade onclick={() => onClose?.()} role="presentation"></div>
  <div class="sheet" transition:fly={{ y: 320 }} role="dialog" aria-modal="true">
    <span class="grab"></span>
    {@render children()}
  </div>
{/if}

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    z-index: 70;
    background: rgba(0, 0, 0, 0.5);
  }
  .sheet {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 71;
    max-width: 560px;
    margin: 0 auto;
    max-height: 88dvh;
    overflow-y: auto;
    padding: 10px 20px calc(var(--safe-bottom) + 20px);
    background: var(--surface);
    color: var(--text);
    border-radius: 24px 24px 0 0;
    display: grid;
    gap: 12px;
    box-shadow: 0 -10px 40px rgba(0, 0, 0, 0.25);
  }
  .grab {
    justify-self: center;
    width: 40px;
    height: 5px;
    border-radius: 3px;
    background: var(--line);
  }
</style>
