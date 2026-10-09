<script>
  import { onMount } from 'svelte';
  import Icon from '../../components/Icon.svelte';
  import { api } from '../../lib/api.js';
  import { fly } from '../../lib/motion.js';
  import { go, route } from '../../lib/router.js';
  import { toast } from '../../lib/toast.js';
  import CategoriesAdmin from './CategoriesAdmin.svelte';
  import FeedbackAdmin from './FeedbackAdmin.svelte';
  import LogsAdmin from './LogsAdmin.svelte';
  import SharedUpload from './SharedUpload.svelte';
  import TeamsAdmin from './TeamsAdmin.svelte';

  let authed = $state(null); // null = comprobando
  let password = $state('');
  let busy = $state(false);
  let tab = $state('categorias');
  const shared = $derived(Number($route.query.get('shared') || 0));

  onMount(async () => {
    try {
      authed = (await api('/api/admin/me')).authenticated;
    } catch {
      authed = false;
    }
  });

  async function login(e) {
    e.preventDefault();
    busy = true;
    try {
      await api('/api/admin/login', { method: 'POST', json: { password } });
      authed = true;
      password = '';
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      busy = false;
    }
  }

  async function logout() {
    await api('/api/admin/logout', { method: 'POST' }).catch(() => {});
    authed = false;
  }

  const tabs = [
    { id: 'categorias', label: 'Categorías', icon: 'trophy' },
    { id: 'equipos', label: 'Equipos', icon: 'ball' },
    { id: 'feedback', label: 'Feedback', icon: 'inbox' },
    { id: 'registro', label: 'Registro', icon: 'list' },
  ];
</script>

<div class="page admin">
  <header class="head">
    <button class="back" onclick={() => go('/')} aria-label="Salir del admin"><Icon name="back" size={24} /></button>
    <h1>Administración</h1>
    {#if authed}
      <button class="btn small ghost" onclick={logout}><Icon name="logout" size={16} /> Salir</button>
    {/if}
  </header>

  {#if authed === null}
    <div class="skeleton" style="height:200px"></div>
  {:else if !authed}
    <form class="card login" onsubmit={login} in:fly>
      <img src="/logo-256.webp" alt="" width="72" height="72" />
      {#if shared}
        <p class="muted">Inicia sesión para subir los {shared} fichero(s) compartido(s).</p>
      {/if}
      <div class="field">
        <label for="pw">Contraseña de administrador</label>
        <input id="pw" class="input" type="password" bind:value={password} autocomplete="current-password" required />
      </div>
      <button class="btn primary" disabled={busy}>{busy ? 'Entrando…' : 'Entrar'}</button>
    </form>
  {:else}
    {#if shared}
      <SharedUpload count={shared} onDone={() => go('/admin', { replace: true })} />
    {/if}

    <div class="tabs">
      {#each tabs as t}
        <button class:on={tab === t.id} onclick={() => (tab = t.id)}><Icon name={t.icon} size={17} /> {t.label}</button>
      {/each}
    </div>

    {#key tab}
      <div in:fly={{ y: 10 }}>
        {#if tab === 'categorias'}
          <CategoriesAdmin />
        {:else if tab === 'equipos'}
          <TeamsAdmin />
        {:else if tab === 'feedback'}
          <FeedbackAdmin />
        {:else}
          <LogsAdmin />
        {/if}
      </div>
    {/key}
  {/if}
</div>

<style>
  .head {
    display: flex;
    align-items: center;
    gap: 8px;
    padding-top: calc(var(--safe-top) + 4px);
    margin-bottom: 16px;
  }
  .head h1 {
    flex: 1;
    font-size: 22px;
    font-weight: 850;
  }
  .back {
    width: 40px;
    height: 40px;
    display: grid;
    place-items: center;
    border-radius: 50%;
  }
  .login {
    display: grid;
    gap: 8px;
    padding: 24px 20px;
    justify-items: stretch;
  }
  .login img {
    justify-self: center;
    border-radius: 50%;
    margin-bottom: 8px;
  }
  .tabs {
    display: flex;
    gap: 8px;
    overflow-x: auto;
    margin-bottom: 16px;
    scrollbar-width: none;
  }
  .tabs button {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 9px 14px;
    border-radius: 999px;
    background: var(--surface);
    border: 1px solid var(--line);
    font-weight: 650;
    font-size: 14px;
    white-space: nowrap;
  }
  .tabs button.on {
    background: var(--brand);
    border-color: var(--brand);
    color: #fff;
  }
</style>
