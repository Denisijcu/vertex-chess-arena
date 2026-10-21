import type { BackendConfig } from './backend-config.model';

/** Build pública (Netlify): backend en el Space de Hugging Face con ZeroGPU. */
export const BACKEND: BackendConfig = {
  kind: 'space',
  space: 'Denisijcu/vertex-chess-arena',
  label: 'Servidor',
};
