<script>
  import Icon from '../components/Icon.svelte';
  import { onMount } from 'svelte';
  import { api } from '../lib/api.js';
  import { joinScorer, leaveScorer, refreshScorer, scorer } from '../lib/scorer.js';
  import { fly, pop } from '../lib/motion.js';
  import { shareApp } from '../lib/share.js';
  import { toast } from '../lib/toast.js';

  const version = __APP_VERSION__;

  const socials = [
    { name: 'Instagram', handle: '@voleibolancares', icon: 'instagram', href: 'https://www.instagram.com/voleibolancares/', cls: 'ig' },
    { name: 'Facebook', handle: 'voleibolancares', icon: 'facebook', href: 'https://www.facebook.com/voleibolancares/', cls: 'fb' },
  ];

  const kinds = [
    { id: 'mejora', label: '💡 Idea o mejora' },
    { id: 'error', label: '🐞 Algo falla' },
    { id: 'otro', label: '💬 Otro' },
  ];

  let form = $state({ kind: 'mejora', name: '', contact: '', message: '', website: '' });
  let sending = $state(false);
  let sent = $state(false);

  // --- funciones extra: código de anotador ---
  let code = $state('');
  let joining = $state(false);
  onMount(refreshScorer);

  async function join(e) {
    e.preventDefault();
    joining = true;
    try {
      const r = await joinScorer(code);
      code = '';
      toast(`¡Hola, ${r.name}! Ya puedes publicar resultados provisionales`, 'ok', 4000);
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      joining = false;
    }
  }

  async function submit(e) {
    e.preventDefault();
    if (form.message.trim().length < 3) {
      toast('Escribe un poco más 🙂', 'error');
      return;
    }
    sending = true;
    try {
      await api('/api/feedback', { method: 'POST', json: form });
      sent = true;
      form = { kind: 'mejora', name: '', contact: '', message: '', website: '' };
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      sending = false;
    }
  }
</script>

<div class="page">
  <header class="club" in:fly={{ y: -10 }}>
    <img src="/logo-256.webp" alt="Escudo del Voleibol Ancares" width="120" height="120" in:pop />
    <h1>Voleibol Ancares</h1>
    <p class="muted">Sigue al club en sus redes</p>
  </header>

  <div class="socials">
    {#each socials as s, i}
      <a class="social card {s.cls}" href={s.href} target="_blank" rel="noopener" in:fly={{ y: 16, delay: 100 + i * 70 }}>
        <span class="ico"><Icon name={s.icon} size={24} /></span>
        <span class="txt"><b>{s.name}</b><span class="muted">{s.handle}</span></span>
        <Icon name="external" size={18} />
      </a>
    {/each}
  </div>

  <button class="btn ghost wide" onclick={shareApp}><Icon name="share" size={18} /> Compartir la app con otras familias</button>

  <h2 class="section-title">Sobre esta app</h2>
  <div class="card notice" in:fly={{ y: 16, delay: 200 }}>
    <Icon name="info" size={22} />
    <div>
      <p><b>App no oficial.</b> No pertenece al club ni a la federación: la ha hecho un padre del equipo en su tiempo libre para que las familias sigamos a nuestras jugadoras.</p>
      <p>Los datos salen de la <a href="https://fvcl.es" target="_blank" rel="noopener">Federación de Voleibol de Castilla y León</a> y se actualizan una vez al día. Puede haber retrasos o errores; <b>si hay dudas, manda la web oficial</b>.</p>
      <p class="muted small">Se ofrece tal cual, sin garantía de ningún tipo.</p>
    </div>
  </div>

  <h2 class="section-title">Comentarios y mejoras</h2>
  {#if sent}
    <div class="card thanks" in:pop>
      <span class="big">💚</span>
      <b>¡Gracias por escribir!</b>
      <p class="muted">Lo leeré en cuanto pueda. Recuerda que esto se hace en ratos libres, así que puede tardar un poco.</p>
      <button class="btn small" onclick={() => (sent = false)}>Enviar otro</button>
    </div>
  {:else}
    <form class="card feedback" onsubmit={submit}>
      <div class="kinds" role="radiogroup" aria-label="Tipo de comentario">
        {#each kinds as k}
          <button type="button" role="radio" aria-checked={form.kind === k.id} class:on={form.kind === k.id} onclick={() => (form.kind = k.id)}>
            {k.label}
          </button>
        {/each}
      </div>
      <div class="field">
        <label for="fb-msg">Mensaje</label>
        <textarea id="fb-msg" class="input" bind:value={form.message} maxlength="4000" placeholder="¿Qué te gustaría ver? ¿Algo no funciona bien?" required></textarea>
      </div>
      <div class="two">
        <div class="field">
          <label for="fb-name">Nombre <span class="opt">(opcional)</span></label>
          <input id="fb-name" class="input" bind:value={form.name} maxlength="100" autocomplete="name" />
        </div>
        <div class="field">
          <label for="fb-contact">Email o teléfono <span class="opt">(opcional)</span></label>
          <input id="fb-contact" class="input" bind:value={form.contact} maxlength="200" autocomplete="email" />
        </div>
      </div>
      <!-- honeypot anti-spam: invisible para personas -->
      <input class="hp" tabindex="-1" autocomplete="off" bind:value={form.website} aria-hidden="true" />
      <button class="btn primary wide" disabled={sending}>
        <Icon name="send" size={18} />
        {sending ? 'Enviando…' : 'Enviar'}
      </button>
    </form>
  {/if}

  <h2 class="section-title">Funciones extra</h2>
  <div class="card extra">
    {#if $scorer.scorer}
      <div class="extra-on">
        <span class="key"><Icon name="key" size={20} /></span>
        <div>
          <b>Eres anotador/a: {$scorer.name}</b>
          <p class="muted">Puedes publicar resultados provisionales desde el <a href="#/marcador">Marcador</a>.</p>
        </div>
      </div>
      <button class="btn small ghost" onclick={leaveScorer}>Desactivar en este móvil</button>
    {:else}
      <p class="muted">¿Te ha dado el administrador un código de anotador? Introdúcelo aquí para publicar resultados provisionales desde el Marcador.</p>
      <form class="code-form" onsubmit={join}>
        <input
          class="input code"
          bind:value={code}
          placeholder="XXXX-XXXX"
          autocomplete="off"
          autocapitalize="characters"
          spellcheck="false"
          maxlength="12"
          aria-label="Código de anotador"
          required
        />
        <button class="btn primary" disabled={joining || code.trim().length < 4}>{joining ? '…' : 'Activar'}</button>
      </form>
    {/if}
  </div>

  <p class="footer muted">Hecho con 💚 por familias del club · v{version}</p>
</div>

<style>
  .club {
    display: grid;
    justify-items: center;
    text-align: center;
    gap: 4px;
    padding-top: calc(var(--safe-top) + 12px);
  }
  .club img {
    border-radius: 50%;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.18);
    margin-bottom: 10px;
  }
  h1 {
    font-size: 24px;
    font-weight: 850;
  }
  .club p {
    margin: 0;
  }
  .socials {
    display: grid;
    gap: 10px;
    margin: 22px 0 12px;
  }
  .social {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 12px 14px;
    color: var(--text);
    text-decoration: none;
    transition: transform 0.15s var(--ease-out);
  }
  .social:active {
    transform: scale(0.98);
  }
  .social > :global(svg) {
    color: var(--muted);
  }
  .ico {
    width: 46px;
    height: 46px;
    border-radius: 14px;
    display: grid;
    place-items: center;
    color: #fff;
  }
  .ig .ico {
    background: radial-gradient(circle at 30% 107%, #fdf497 0%, #fd5949 45%, #d6249f 60%, #285aeb 90%);
  }
  .fb .ico {
    background: #1877f2;
  }
  .txt {
    flex: 1;
    display: grid;
  }
  .txt span {
    font-size: 13.5px;
  }
  .wide {
    width: 100%;
  }
  .notice {
    display: flex;
    gap: 12px;
    padding: 16px;
    font-size: 14.5px;
    line-height: 1.5;
  }
  .notice > :global(svg) {
    flex: none;
    color: var(--brand);
    margin-top: 2px;
  }
  .notice p {
    margin: 0 0 8px;
  }
  .notice p:last-child {
    margin: 0;
  }
  .small {
    font-size: 13px;
  }
  .feedback {
    padding: 16px;
  }
  .kinds {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 16px;
  }
  .kinds button {
    padding: 8px 12px;
    border-radius: 999px;
    border: 1px solid var(--line);
    font-size: 14px;
    font-weight: 600;
    transition: all 0.2s;
  }
  .kinds button.on {
    background: var(--brand-soft);
    border-color: var(--brand);
    color: var(--brand-strong);
  }
  .two {
    display: grid;
    gap: 0 12px;
  }
  @media (min-width: 520px) {
    .two {
      grid-template-columns: 1fr 1fr;
    }
  }
  .opt {
    font-weight: 500;
    opacity: 0.8;
  }
  .hp {
    position: absolute;
    left: -9999px;
    width: 1px;
    height: 1px;
    opacity: 0;
  }
  .thanks {
    display: grid;
    justify-items: center;
    gap: 6px;
    padding: 24px 20px;
    text-align: center;
  }
  .thanks p {
    margin: 0 0 8px;
  }
  .big {
    font-size: 40px;
  }
  .extra {
    padding: 16px;
    display: grid;
    gap: 12px;
    font-size: 14.5px;
  }
  .extra p {
    margin: 0;
  }
  .extra-on {
    display: flex;
    gap: 12px;
    align-items: flex-start;
  }
  .key {
    width: 40px;
    height: 40px;
    border-radius: 12px;
    display: grid;
    place-items: center;
    flex: none;
    background: var(--brand);
    color: #fff;
  }
  .code-form {
    display: flex;
    gap: 8px;
  }
  .code {
    flex: 1;
    min-width: 0;
    font-family: ui-monospace, 'SF Mono', Menlo, monospace;
    font-size: 18px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }
  .footer {
    text-align: center;
    font-size: 12.5px;
    margin-top: 28px;
  }
</style>
