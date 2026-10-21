import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  OnDestroy,
  afterNextRender,
  effect,
  input,
  output,
  viewChild,
} from '@angular/core';
import { BORDER_TYPE, Chessboard, INPUT_EVENT_TYPE, MoveInputEvent } from 'cm-chessboard/src/Chessboard.js';
import { Markers } from 'cm-chessboard/src/extensions/markers/Markers.js';
import {
  PROMOTION_DIALOG_RESULT_TYPE,
  PromotionDialog,
} from 'cm-chessboard/src/extensions/promotion-dialog/PromotionDialog.js';
import { Side } from '../core/models';

// Tipos de marcador: deben ser referencias únicas (cm-chessboard compara por referencia).
const MARKER_LAST = { class: 'marker-last-move', slice: 'markerSquare' };
const MARKER_CHECK = { class: 'marker-check', slice: 'markerSquare' };
const MARKER_LEGAL = { class: 'marker-legal', slice: 'markerDot' };
const MARKER_SELECTED = { class: 'marker-selected', slice: 'markerSquare' };

export interface BoardMove {
  from: string;
  to: string;
  promotion?: string;
}

/**
 * Tablero SVG (cm-chessboard, MIT) con piezas Cburnett (CC BY-SA 3.0).
 * El componente es "tonto": pinta el FEN que recibe y propone jugadas; quien lo usa decide
 * si son legales con `tryMove`.
 */
@Component({
  selector: 'vx-chessboard',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<div #host class="w-full aspect-square select-none" role="application" [attr.aria-label]="ariaLabel()"></div>`,
})
export class ChessboardComponent implements OnDestroy {
  readonly fen = input.required<string>();
  readonly orientation = input<Side>('w');
  /** Lado que puede mover con el ratón; null = solo lectura. */
  readonly interactive = input<Side | null>(null);
  readonly lastMove = input<{ from: string; to: string } | null>(null);
  readonly checkSquare = input<string | null>(null);
  readonly legalTargets = input<(square: string) => string[]>(() => []);
  readonly isPromotion = input<(from: string, to: string) => boolean>(() => false);
  readonly tryMove = input<(m: BoardMove) => boolean>(() => false);
  readonly ariaLabel = input('Tablero de ajedrez');
  readonly moved = output<BoardMove>();

  private readonly host = viewChild.required<ElementRef<HTMLDivElement>>('host');
  private board: Chessboard | null = null;
  private ready = false;

  constructor() {
    afterNextRender(() => {
      this.board = new Chessboard(this.host().nativeElement, {
        position: this.fen(),
        orientation: this.orientation(),
        assetsUrl: '/cm-assets/',
        responsive: true,
        style: {
          cssClass: 'vertex',
          showCoordinates: true,
          borderType: BORDER_TYPE.none,
          pieces: { file: 'pieces/standard.svg' },
          animationDuration: 160,
        },
        extensions: [
          { class: Markers, props: { autoMarkers: null } },
          { class: PromotionDialog, props: { language: 'en' } },
        ],
      });
      this.ready = true;
      this.syncInput();
      this.syncMarkers();
    });

    effect(() => {
      const fen = this.fen();
      if (this.ready && this.board && this.board.getPosition() !== fen.split(' ')[0]) {
        void this.board.setPosition(fen, true);
      }
    });
    effect(() => {
      const o = this.orientation();
      if (this.ready) void this.board?.setOrientation(o, false);
    });
    effect(() => {
      this.interactive();
      this.syncInput();
    });
    effect(() => {
      this.lastMove();
      this.checkSquare();
      this.syncMarkers();
    });
  }

  private syncMarkers(): void {
    const b = this.board;
    if (!this.ready || !b) return;
    b.removeMarkers(MARKER_LAST);
    b.removeMarkers(MARKER_CHECK);
    const lm = this.lastMove();
    if (lm) {
      b.addMarker(MARKER_LAST, lm.from);
      b.addMarker(MARKER_LAST, lm.to);
    }
    const chk = this.checkSquare();
    if (chk) b.addMarker(MARKER_CHECK, chk);
  }

  private clearInputMarkers(): void {
    this.board?.removeMarkers(MARKER_LEGAL);
    this.board?.removeMarkers(MARKER_SELECTED);
  }

  private syncInput(): void {
    const b = this.board;
    if (!this.ready || !b) return;
    if (b.isMoveInputEnabled()) b.disableMoveInput();
    this.clearInputMarkers();
    const side = this.interactive();
    if (!side) return;
    b.enableMoveInput((e: MoveInputEvent) => this.onInput(e), side);
  }

  private onInput(e: MoveInputEvent): boolean | void {
    const b = this.board!;
    switch (e.type) {
      case INPUT_EVENT_TYPE.moveInputStarted: {
        const targets = this.legalTargets()(e.squareFrom);
        if (!targets.length) return false;
        this.clearInputMarkers();
        b.addMarker(MARKER_SELECTED, e.squareFrom);
        for (const t of targets) b.addMarker(MARKER_LEGAL, t);
        return true;
      }
      case INPUT_EVENT_TYPE.validateMoveInput: {
        this.clearInputMarkers();
        const from = e.squareFrom;
        const to = e.squareTo!;
        if (!this.legalTargets()(from).includes(to)) return false;
        if (this.isPromotion()(from, to)) {
          const color = this.interactive() ?? 'w';
          b.showPromotionDialog(to, color, (r) => {
            if (r.type === PROMOTION_DIALOG_RESULT_TYPE.pieceSelected && r.piece) {
              this.commit({ from, to, promotion: r.piece.charAt(1) });
            }
            // Si se canceló o fue ilegal, el tablero vuelve al FEN real.
            void b.setPosition(this.fen(), false);
          });
          return true;
        }
        return this.commit({ from, to });
      }
      case INPUT_EVENT_TYPE.moveInputCanceled:
        this.clearInputMarkers();
        return;
    }
  }

  private commit(m: BoardMove): boolean {
    const ok = this.tryMove()(m);
    if (ok) this.moved.emit(m);
    return ok;
  }

  ngOnDestroy(): void {
    this.board?.destroy();
    this.board = null;
  }
}
