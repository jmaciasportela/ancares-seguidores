<script>
  import TeamBadge from './TeamBadge.svelte';
  import { shortTeam } from '../lib/format.js';
  import { pop } from '../lib/motion.js';

  let { team, points, sets = 0, setsToWin = null, serving = false, tone = 'dark', hint = '', onTap } = $props();

  // Evita sumar dos puntos por un doble toque accidental
  let last = 0;
  function tap() {
    const now = performance.now();
    if (now - last < 300) return;
    last = now;
    onTap?.();
  }
</script>

<button class="pad {tone}" onclick={tap} aria-label="Punto para {team.name}. Lleva {points}">
  <div class="head">
    <TeamBadge name={team.name} logo={team.logo} size={34} />
    <span class="name ellipsis">{shortTeam(team.name)}</span>
    {#if serving}<span class="serve" title="Saca">🏐</span>{/if}
  </div>

  <div class="num-wrap">
    {#key points}
      <b class="num" in:pop={{ start: 0.6, duration: 260 }}>{points}</b>
    {/key}
  </div>

  <div class="foot">
    <span class="sets" aria-label="Sets ganados: {sets}">
      {#if setsToWin}
        {#each Array(setsToWin) as _, i}<i class:on={i < sets}></i>{/each}
      {:else}
        Sets: {sets}
      {/if}
    </span>
    {#if hint}<span class="hint">{hint}</span>{/if}
  </div>
</button>

<style>
  .pad {
    position: relative;
    display: grid;
    grid-template-rows: auto 1fr auto;
    width: 100%;
    min-height: 0;
    padding: 14px 18px;
    color: #fff;
    text-align: left;
    touch-action: manipulation;
    user-select: none;
    -webkit-user-select: none;
    overflow: hidden;
    transition: filter 0.15s;
  }
  .pad:active {
    filter: brightness(1.12);
  }
  .pad.green {
    background:
      radial-gradient(120% 90% at 0% 0%, rgba(255, 255, 255, 0.18), transparent 55%),
      linear-gradient(160deg, #3bbf50, #1f7f30);
  }
  .pad.dark {
    background:
      radial-gradient(120% 90% at 100% 0%, rgba(49, 169, 67, 0.25), transparent 60%),
      linear-gradient(160deg, #173a22, #0b1a10);
  }
  .head {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
  }
  .name {
    font-size: 18px;
    font-weight: 750;
    min-width: 0;
  }
  .serve {
    margin-left: auto;
    font-size: 20px;
    animation: bounce 1.4s infinite;
  }
  @keyframes bounce {
    50% {
      transform: translateY(-3px);
    }
  }
  .num-wrap {
    display: grid;
    place-items: center;
    min-height: 0;
  }
  .num {
    font-size: min(30vw, 26dvh);
    font-weight: 850;
    line-height: 1;
    font-variant-numeric: tabular-nums;
    letter-spacing: -0.04em;
    text-shadow: 0 6px 30px rgba(0, 0, 0, 0.25);
  }
  .foot {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    min-height: 28px;
  }
  .sets {
    display: flex;
    gap: 6px;
    font-weight: 700;
    opacity: 0.9;
  }
  .sets i {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    border: 2px solid rgba(255, 255, 255, 0.7);
  }
  .sets i.on {
    background: #fff;
    border-color: #fff;
  }
  .hint {
    padding: 4px 10px;
    border-radius: 999px;
    background: #fff;
    color: #0b1a10;
    font-size: 12.5px;
    font-weight: 800;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    animation: pulse 1.1s infinite;
  }
  @keyframes pulse {
    50% {
      opacity: 0.6;
    }
  }
</style>
