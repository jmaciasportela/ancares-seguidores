import { writable } from 'svelte/store';

function parse() {
  const hash = location.hash.slice(1) || '/';
  const [path, qs] = hash.split('?');
  return { path, parts: path.split('/').filter(Boolean), query: new URLSearchParams(qs || '') };
}

export const route = writable(parse());
let internalSteps = 0; // navegaciones dentro de la app (para saber si "atrás" sale de ella)

addEventListener('hashchange', () => {
  internalSteps++;
  route.set(parse());
});

export function go(path, { replace = false } = {}) {
  if (replace) {
    history.replaceState(null, '', '#' + path);
    route.set(parse());
  } else {
    location.hash = path;
  }
}

export function back(fallback = '/') {
  if (internalSteps > 0) history.back();
  else go(fallback, { replace: true });
}
