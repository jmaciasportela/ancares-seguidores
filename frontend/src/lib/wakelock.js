/** Mantiene la pantalla encendida (marcador y visor en directo). Devuelve la función para soltarla. */
export function keepScreenOn() {
  if (!('wakeLock' in navigator)) return () => {};
  let lock = null;
  const acquire = async () => {
    try {
      if (document.visibilityState === 'visible') lock = await navigator.wakeLock.request('screen');
    } catch {
      /* el navegador puede denegarlo: no es grave */
    }
  };
  acquire();
  document.addEventListener('visibilitychange', acquire);
  return () => {
    document.removeEventListener('visibilitychange', acquire);
    lock?.release?.();
  };
}
