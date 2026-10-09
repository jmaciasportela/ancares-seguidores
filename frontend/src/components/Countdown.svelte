<script>
  import { countdownParts } from '../lib/format.js';

  let { iso } = $props();
  let now = $state(Date.now());
  const parts = $derived(countdownParts(iso, now));
  // Segundo a segundo solo en la última hora; si no, cada 30 s
  const tickMs = $derived(parts && parts.d === 0 && parts.h === 0 ? 1000 : 30000);

  $effect(() => {
    const timer = setInterval(() => (now = Date.now()), tickMs);
    return () => clearInterval(timer);
  });

  const pad = (n) => String(n).padStart(2, '0');
</script>

{#if parts}
  <div class="cd" role="timer" aria-label="Cuenta atrás">
    {#if parts.d > 0}
      <div class="unit"><b>{parts.d}</b><span>{parts.d === 1 ? 'día' : 'días'}</span></div>
    {/if}
    <div class="unit"><b>{pad(parts.h)}</b><span>h</span></div>
    <div class="unit"><b>{pad(parts.m)}</b><span>min</span></div>
    {#if parts.d === 0}
      <div class="unit"><b>{pad(parts.s)}</b><span>s</span></div>
    {/if}
  </div>
{:else if iso}
  <div class="live"><span class="dot"></span> En juego o recién terminado</div>
{/if}

<style>
  .cd {
    display: flex;
    gap: 8px;
  }
  .unit {
    min-width: 54px;
    padding: 8px 6px 6px;
    border-radius: 12px;
    background: rgba(255, 255, 255, 0.1);
    backdrop-filter: blur(6px);
    text-align: center;
    display: grid;
    gap: 2px;
  }
  b {
    font-size: 22px;
    font-weight: 800;
    font-variant-numeric: tabular-nums;
    line-height: 1;
  }
  span {
    font-size: 11px;
    opacity: 0.75;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .live {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-weight: 700;
  }
  .dot {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    background: var(--danger);
    animation: pulse 1.2s infinite;
  }
  @keyframes pulse {
    50% {
      opacity: 0.3;
    }
  }
</style>
