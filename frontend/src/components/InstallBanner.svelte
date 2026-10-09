<script>
  import Icon from './Icon.svelte';
  import { dismissInstall, installDismissed, installPrompt, isIOS, isStandalone, promptInstall } from '../lib/install.js';
  import { fly, fade } from '../lib/motion.js';

  let hidden = $state(isStandalone || installDismissed());
  let showIOSHelp = $state(false);
  const canInstall = $derived(!hidden && ($installPrompt || isIOS));

  async function install() {
    if ($installPrompt) {
      await promptInstall($installPrompt);
    } else if (isIOS) {
      showIOSHelp = true;
    }
  }

  function close() {
    dismissInstall();
    hidden = true;
  }
</script>

{#if canInstall}
  <div class="banner card" transition:fly={{ y: 20 }}>
    <img src="/logo-256.webp" alt="" width="44" height="44" />
    <div class="txt">
      <b>Instala la app</b>
      <span>Ábrela como una app más, sin pasar por el navegador.</span>
    </div>
    <button class="btn primary small" onclick={install}>Instalar</button>
    <button class="close" onclick={close} aria-label="Ahora no"><Icon name="x" size={18} /></button>
  </div>
{/if}

{#if showIOSHelp}
  <div class="backdrop" transition:fade onclick={() => (showIOSHelp = false)} role="presentation"></div>
  <div class="sheet" transition:fly={{ y: 300 }} role="dialog" aria-modal="true" aria-labelledby="ios-title">
    <span class="grab"></span>
    <h3 id="ios-title">Instalar en iPhone</h3>
    <ol>
      <li>Abre esta página en <b>Safari</b>.</li>
      <li>Pulsa el botón <b>Compartir</b> <span class="ios-share"><Icon name="share" size={16} /></span> de la barra inferior.</li>
      <li>Elige <b>«Añadir a pantalla de inicio»</b>.</li>
      <li>Pulsa <b>Añadir</b>. ¡Listo! 🏐</li>
    </ol>
    <button class="btn primary" onclick={() => { showIOSHelp = false; close(); }}>Entendido</button>
  </div>
{/if}

<style>
  .banner {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px;
    margin-bottom: 16px;
  }
  img {
    border-radius: 50%;
    flex: none;
  }
  .txt {
    flex: 1;
    min-width: 0;
    display: grid;
    font-size: 13px;
    color: var(--muted);
  }
  .txt b {
    color: var(--text);
    font-size: 15px;
  }
  .close {
    color: var(--muted);
    width: 32px;
    height: 32px;
    display: grid;
    place-items: center;
    flex: none;
  }
  .backdrop {
    position: fixed;
    inset: 0;
    z-index: 40;
    background: rgba(0, 0, 0, 0.45);
  }
  .sheet {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 41;
    padding: 12px 24px calc(var(--safe-bottom) + 24px);
    background: var(--surface);
    border-radius: 24px 24px 0 0;
    display: grid;
    gap: 12px;
    max-width: 560px;
    margin: 0 auto;
  }
  .grab {
    justify-self: center;
    width: 40px;
    height: 5px;
    border-radius: 3px;
    background: var(--line);
  }
  ol {
    margin: 0;
    padding-left: 20px;
    display: grid;
    gap: 10px;
    line-height: 1.45;
  }
  .ios-share {
    display: inline-grid;
    place-items: center;
    vertical-align: -3px;
    color: #0a84ff;
  }
</style>
