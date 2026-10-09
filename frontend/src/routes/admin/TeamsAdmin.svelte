<script>
  import { onMount } from 'svelte';
  import { slide } from 'svelte/transition';
  import Icon from '../../components/Icon.svelte';
  import TeamBadge from '../../components/TeamBadge.svelte';
  import { api } from '../../lib/api.js';
  import { fly, reduced } from '../../lib/motion.js';
  import { toast } from '../../lib/toast.js';

  const SOURCE = { manual: 'Subido', fvcl: 'FVCL' };

  let teams = $state([]);
  let loading = $state(true);
  let onlyMissing = $state(false);
  let searching = $state(false);
  let busy = $state(null); // id del equipo en curso
  let urlFor = $state(null); // id con el campo de URL abierto
  let urlValue = $state('');

  const visible = $derived(onlyMissing ? teams.filter((t) => !t.logo && !t.is_ours) : teams);
  const missing = $derived(teams.filter((t) => !t.logo && !t.is_ours).length);

  async function load() {
    try {
      teams = await api('/api/admin/teams');
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      loading = false;
    }
  }
  onMount(load);

  async function searchFvcl() {
    searching = true;
    try {
      const { reports } = await api('/api/admin/teams/search-fvcl', { method: 'POST', json: { force: true } });
      const found = reports.reduce((n, r) => n + r.found.length, 0);
      const errors = reports.filter((r) => r.error);
      if (errors.length) toast(`No se pudo leer la FVCL: ${errors[0].error}`, 'error', 6000);
      else toast(found ? `${found} logo(s) encontrados` : 'No se encontraron logos nuevos', found ? 'ok' : 'error');
      await load();
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      searching = false;
    }
  }

  async function upload(team, event) {
    const file = event.currentTarget.files[0];
    event.currentTarget.value = '';
    if (!file) return;
    busy = team.id;
    const form = new FormData();
    form.append('file', file);
    try {
      await api(`/api/admin/teams/${team.id}/logo`, { method: 'POST', form });
      toast('Logo guardado', 'ok');
      await load();
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      busy = null;
    }
  }

  async function fromUrl(team, e) {
    e.preventDefault();
    busy = team.id;
    try {
      await api(`/api/admin/teams/${team.id}/logo-url`, { method: 'POST', json: { url: urlValue } });
      toast('Logo guardado', 'ok');
      urlFor = null;
      urlValue = '';
      await load();
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      busy = null;
    }
  }

  async function remove(team) {
    busy = team.id;
    try {
      await api(`/api/admin/teams/${team.id}/logo`, { method: 'DELETE' });
      await load();
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      busy = null;
    }
  }
</script>

<div class="toolbar">
  <button class="btn primary small" onclick={searchFvcl} disabled={searching || !teams.length}>
    <Icon name="refresh" size={16} />
    {searching ? 'Buscando…' : 'Buscar logos en la FVCL'}
  </button>
  <label class="check">
    <input type="checkbox" bind:checked={onlyMissing} />
    Solo sin logo ({missing})
  </label>
</div>
<p class="muted hint">
  El botón vuelve a buscar los que faltan y rehace los que vinieron de la FVCL; nunca toca un logo subido a mano. Si un escudo no aparece o sale mal, súbelo o pega el enlace de la imagen (PNG, JPG o WebP).
</p>

{#if loading}
  <div class="skeleton" style="height:200px"></div>
{:else if !teams.length}
  <div class="card empty muted">Aún no hay equipos: importa primero alguna clasificación.</div>
{/if}

<div class="list">
  {#each visible as team, i (team.id)}
    <article class="card team" in:fly={{ y: 10, delay: Math.min(i * 30, 300) }}>
      <div class="head">
        <TeamBadge name={team.name} logo={team.logo} size={44} />
        <div class="info">
          <b class="ellipsis">{team.name}</b>
          <span class="muted small ellipsis">{team.categories.join(' · ')}</span>
        </div>
        {#if team.is_ours}
          <span class="chip brand">Nuestro</span>
        {:else if team.logo}
          <span class="chip brand">{SOURCE[team.logo_source] || 'Logo'}</span>
        {:else}
          <span class="chip">Sin logo</span>
        {/if}
      </div>

      {#if !team.is_ours}
        <div class="actions">
          <label class="btn small" class:disabled={busy === team.id}>
            <Icon name="upload" size={15} /> Subir
            <input type="file" accept="image/png,image/jpeg,image/webp,image/gif" hidden onchange={(e) => upload(team, e)} />
          </label>
          <button class="btn small" onclick={() => { urlFor = urlFor === team.id ? null : team.id; urlValue = ''; }}>
            <Icon name="external" size={15} /> Enlace
          </button>
          {#if team.logo}
            <button class="btn small danger" onclick={() => remove(team)} disabled={busy === team.id} aria-label="Quitar logo">
              <Icon name="trash" size={15} />
            </button>
          {/if}
        </div>
        {#if urlFor === team.id}
          <form class="url" onsubmit={(e) => fromUrl(team, e)} transition:slide={{ duration: reduced ? 0 : 200 }}>
            <input class="input" type="url" inputmode="url" placeholder="https://…/escudo.png" bind:value={urlValue} required />
            <button class="btn primary small" disabled={busy === team.id}>{busy === team.id ? '…' : 'Guardar'}</button>
          </form>
        {/if}
      {/if}
    </article>
  {/each}
</div>

<style>
  .toolbar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px 14px;
  }
  .check {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    font-weight: 600;
  }
  .check input {
    width: 18px;
    height: 18px;
    accent-color: var(--brand);
  }
  .hint {
    font-size: 13px;
    margin: 10px 2px 14px;
  }
  .list {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    gap: 10px;
  }
  .team {
    padding: 12px 14px;
    min-width: 0;
  }
  .head {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .info {
    flex: 1;
    min-width: 0;
    display: grid;
  }
  .small {
    font-size: 12.5px;
  }
  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 10px;
  }
  .url {
    display: flex;
    gap: 8px;
    margin-top: 10px;
  }
  .url .input {
    min-height: 40px;
    flex: 1;
    min-width: 0;
  }
  .disabled {
    opacity: 0.6;
    pointer-events: none;
  }
  .empty {
    padding: 24px;
    text-align: center;
  }
</style>
