<script>
  import { onMount } from 'svelte';
  import Icon from '../../components/Icon.svelte';
  import { api } from '../../lib/api.js';
  import { timeAgo } from '../../lib/format.js';
  import { fly } from '../../lib/motion.js';
  import { toast } from '../../lib/toast.js';

  const KIND = { error: '🐞 Error', mejora: '💡 Mejora', otro: '💬 Otro' };
  let items = $state([]);
  let loading = $state(true);

  onMount(async () => {
    try {
      items = await api('/api/admin/feedback');
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      loading = false;
    }
  });

  async function toggle(item) {
    const updated = await api(`/api/admin/feedback/${item.id}`, { method: 'PATCH', json: { read: !item.read } });
    items = items.map((i) => (i.id === item.id ? updated : i));
  }

  async function remove(item) {
    await api(`/api/admin/feedback/${item.id}`, { method: 'DELETE' });
    items = items.filter((i) => i.id !== item.id);
  }
</script>

{#if loading}
  <div class="skeleton" style="height:120px"></div>
{:else if !items.length}
  <div class="card empty"><Icon name="inbox" size={32} /><p>No hay comentarios todavía.</p></div>
{/if}

<div class="list">
  {#each items as item, i (item.id)}
    <article class="card fb" class:read={item.read} in:fly={{ y: 10, delay: i * 40 }}>
      <header>
        <span class="chip">{KIND[item.kind] || item.kind}</span>
        <span class="muted small">{timeAgo(item.created_at)}</span>
      </header>
      <p class="msg">{item.message}</p>
      {#if item.name || item.contact}
        <p class="muted small">{item.name || 'Anónimo'}{item.contact ? ` · ${item.contact}` : ''}</p>
      {/if}
      <div class="actions">
        <button class="btn small" onclick={() => toggle(item)}>
          <Icon name="check" size={16} />
          {item.read ? 'Marcar no leído' : 'Marcar leído'}
        </button>
        <button class="btn small danger" onclick={() => remove(item)} aria-label="Eliminar"><Icon name="trash" size={16} /></button>
      </div>
    </article>
  {/each}
</div>

<style>
  .list {
    display: grid;
    gap: 10px;
  }
  .fb {
    padding: 14px 16px;
    border-left: 4px solid var(--brand);
  }
  .fb.read {
    border-left-color: var(--line);
    opacity: 0.75;
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .msg {
    white-space: pre-wrap;
    margin: 10px 0;
    line-height: 1.5;
  }
  .small {
    font-size: 13px;
    margin: 0;
  }
  .actions {
    display: flex;
    gap: 8px;
    margin-top: 10px;
  }
  .empty {
    display: grid;
    justify-items: center;
    padding: 30px;
    color: var(--muted);
  }
</style>
