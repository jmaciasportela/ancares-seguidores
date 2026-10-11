<script>
  import { PRESETS, describeFormat, presetOf } from '../lib/scoring.js';

  let { value = $bindable() } = $props();
  const current = $derived(presetOf(value));
  let custom = $state(false);
  const showCustom = $derived(custom || current === 'custom');

  function pick(preset) {
    custom = false;
    value = { ...preset.format };
  }

  function set(key, v) {
    value = { ...value, [key]: v };
  }
</script>

<div class="formats" role="radiogroup" aria-label="Formato del partido">
  {#each PRESETS as p}
    <button type="button" role="radio" aria-checked={current === p.id && !custom} class:on={current === p.id && !custom} onclick={() => pick(p)}>
      <b>{p.label}</b><span>{p.detail}</span>
    </button>
  {/each}
  <button type="button" role="radio" aria-checked={showCustom} class:on={showCustom} onclick={() => (custom = true)}>
    <b>Personalizado</b><span>{showCustom ? describeFormat(value) : 'Elige sets y puntos'}</span>
  </button>
</div>

{#if showCustom}
  <div class="custom">
    <label>
      <span>Tipo</span>
      <select class="input" value={value.mode} onchange={(e) => set('mode', e.currentTarget.value)}>
        <option value="best_of">Al mejor de</option>
        <option value="fixed">Sets fijos</option>
      </select>
    </label>
    <label>
      <span>Sets</span>
      <select class="input" value={value.sets} onchange={(e) => set('sets', Number(e.currentTarget.value))}>
        {#each [1, 2, 3, 4, 5] as n}<option value={n}>{n}</option>{/each}
      </select>
    </label>
    <label>
      <span>Puntos por set</span>
      <select class="input" value={value.points} onchange={(e) => set('points', Number(e.currentTarget.value))}>
        {#each [25, 21, 15] as n}<option value={n}>{n}</option>{/each}
      </select>
    </label>
    {#if value.mode === 'best_of'}
      <label>
        <span>Set decisivo</span>
        <select class="input" value={value.tiebreak ?? value.points} onchange={(e) => set('tiebreak', Number(e.currentTarget.value))}>
          {#each [15, 21, 25] as n}<option value={n}>a {n}</option>{/each}
        </select>
      </label>
    {/if}
  </div>
{/if}

<style>
  .formats {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: 8px;
  }
  .formats button {
    display: grid;
    gap: 2px;
    text-align: left;
    padding: 10px 12px;
    border-radius: 14px;
    border: 1.5px solid var(--line);
    background: var(--surface);
    transition: border-color 0.2s, background 0.2s;
  }
  .formats b {
    font-size: 14.5px;
  }
  .formats span {
    font-size: 12.5px;
    color: var(--muted);
  }
  .formats button.on {
    border-color: var(--brand);
    background: var(--brand-soft);
  }
  .custom {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin-top: 12px;
  }
  .custom label {
    display: grid;
    gap: 4px;
    font-size: 13px;
    font-weight: 650;
    color: var(--muted);
  }
</style>
