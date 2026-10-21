import type { BackendConfig } from './backend-config.model';

/** Arena local (FastAPI + Ollama). La build de Netlify reemplaza este archivo por backend-config.netlify.ts. */
export const BACKEND: BackendConfig = { kind: 'local', label: 'Ollama' };
