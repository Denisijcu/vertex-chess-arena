/* Tipos mínimos para cm-chessboard (la librería no trae .d.ts). */
declare module 'cm-chessboard/src/Chessboard.js' {
  export const COLOR: { white: 'w'; black: 'b' };
  export const INPUT_EVENT_TYPE: {
    moveInputStarted: string;
    validateMoveInput: string;
    moveInputCanceled: string;
    moveInputFinished: string;
    movingOverSquare: string;
  };
  export const BORDER_TYPE: { none: string; thin: string; frame: string };
  export interface MoveInputEvent {
    type: string;
    squareFrom: string;
    squareTo?: string;
    piece?: string;
    chessboard: Chessboard;
  }
  export class Chessboard {
    constructor(context: HTMLElement, props?: Record<string, unknown>);
    setPosition(fen: string, animated?: boolean): Promise<void>;
    getPosition(): string;
    setOrientation(color: 'w' | 'b', animated?: boolean): Promise<void>;
    enableMoveInput(handler: (e: MoveInputEvent) => boolean | void, color?: 'w' | 'b'): void;
    disableMoveInput(): void;
    isMoveInputEnabled(): boolean;
    addMarker(type: unknown, square: string): void;
    removeMarkers(type?: unknown, square?: string): void;
    showPromotionDialog(square: string, color: 'w' | 'b', cb: (r: { type: string; piece?: string }) => void): void;
    destroy(): void;
  }
}
declare module 'cm-chessboard/src/extensions/markers/Markers.js' {
  export const Markers: unknown;
}
declare module 'cm-chessboard/src/extensions/promotion-dialog/PromotionDialog.js' {
  export const PromotionDialog: unknown;
  export const PROMOTION_DIALOG_RESULT_TYPE: { pieceSelected: string; canceled: string };
}
