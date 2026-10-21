/**
 * Dónde está el backend.
 * - "local": la API FastAPI de la arena (misma máquina, Ollama). Configuración por defecto.
 * - "space": el Space de Hugging Face con ZeroGPU; partidas y torneos se guardan en el navegador.
 */
export interface BackendConfig {
  kind: 'local' | 'space';
  /** Space de Hugging Face, "usuario/nombre" (solo en modo space). */
  space?: string;
  /** Nombre del servicio en la cabecera: "Ollama conectado", "Servidor conectado". */
  label: string;
}
