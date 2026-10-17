<script>
  import { onMount } from 'svelte';
  import { liveMode, matchState } from '../lib/format.js';

  /** Etiqueta «HOY» / «EN JUEGO» para las tarjetas de los partidos del día (o «EN DIRECTO» / «FINAL» si se retransmite) */
  let { startsAt, live = null } = $props();
  let now = $state(Date.now());
  onMount(() => {
    const t = setInterval(() => (now = Date.now()), 30000);
    return () => clearInterval(t);
  });
  const state = $derived(matchState(startsAt, now));
  const mode = $derived(liveMode(live));
</script>

{#if mode === 'live'}
  <span class="badge live"><i></i> EN DIRECTO</span>
{:else if mode === 'final'}
  <span class="badge">FINAL</span>
{:else if state === 'live'}
  <span class="badge live"><i></i> EN JUEGO</span>
{:else}
  <span class="badge"><span class="ball" aria-hidden="true">🏐</span> HOY</span>
{/if}

<style>
  .badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 3px 9px;
    border-radius: 999px;
    background: #fff;
    color: #1f7f30;
    font-size: 11.5px;
    font-weight: 900;
    letter-spacing: 0.08em;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.18);
  }
  .ball {
    display: inline-block;
    font-size: 12px;
    animation: spin 2.4s linear infinite;
  }
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
  .badge.live {
    color: #d92d33;
  }
  .live i {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #ff3b41;
    animation: blink 1s infinite;
  }
  @keyframes blink {
    50% {
      opacity: 0.25;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .ball,
    .live i {
      animation: none;
    }
  }
</style>
