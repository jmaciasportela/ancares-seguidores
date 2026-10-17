<script>
  import { onMount } from 'svelte';
  import { api } from '../../lib/api.js';
  import { timeAgo } from '../../lib/format.js';
  import { toast } from '../../lib/toast.js';

  const KIND = { ranking: 'Clasificación', calendar: 'Calendario' };
  const SOURCE = { auto: 'automática', manual: 'subida', share: 'compartido' };
  const STATUS = { ok: '🆕 Novedades', unchanged: 'Sin cambios', blocked: 'Bloqueado', error: 'Error' };
  let logs = $state([]);
  let loading = $state(true);

  onMount(async () => {
    try {
      logs = await api('/api/admin/logs?limit=100');
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      loading = false;
    }
  });
</script>

{#if loading}
  <div class="skeleton" style="height:200px"></div>
{:else if !logs.length}
  <div class="card empty muted">Sin actividad todavía.</div>
{:else}
  <div class="card list">
    {#each logs as l (l.id)}
      <div class="log">
        <span class="dot {l.status}"></span>
        <div class="body">
          <div class="line">
            <b class="ellipsis">{l.category || '—'} · {KIND[l.kind] || l.kind}</b>
            <span class="muted small">{timeAgo(l.created_at)}</span>
          </div>
          <span class="small" class:muted={l.status !== 'ok'} class:news={l.status === 'ok'}>
            {STATUS[l.status] || l.status} ({SOURCE[l.source] || l.source}){l.message && l.message !== 'Sin cambios' ? ` — ${l.message}` : ''}
          </span>
          {#if l.details?.length}
            <details>
              <summary class="muted small">Ver {l.details.length} {l.details.length === 1 ? 'cambio' : 'cambios'}</summary>
              <ul>{#each l.details as d}<li>{d}</li>{/each}</ul>
            </details>
          {/if}
        </div>
      </div>
    {/each}
  </div>
{/if}

<style>
  .list {
    padding: 4px 14px;
  }
  .log {
    display: flex;
    gap: 10px;
    padding: 10px 0;
  }
  .log + .log {
    border-top: 1px solid var(--line);
  }
  .dot {
    flex: none;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    margin-top: 6px;
    background: var(--muted);
  }
  .dot.ok {
    background: var(--brand);
  }
  .dot.unchanged {
    background: var(--line);
  }
  .dot.blocked {
    background: var(--warn);
  }
  .dot.error {
    background: var(--danger);
  }
  .body {
    flex: 1;
    min-width: 0;
    display: grid;
    gap: 2px;
  }
  .line {
    display: flex;
    justify-content: space-between;
    gap: 8px;
  }
  .news {
    color: var(--brand-strong);
    font-weight: 600;
  }
  details ul {
    margin: 4px 0 0;
    padding-left: 18px;
    font-size: 12.5px;
    color: var(--muted);
  }
  .small {
    font-size: 12.5px;
    word-break: break-word;
  }
  .empty {
    padding: 24px;
    text-align: center;
  }
</style>
