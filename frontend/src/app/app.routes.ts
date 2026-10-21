import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', title: 'Vertex Chess Arena', loadComponent: () => import('./features/lobby/lobby').then((m) => m.LobbyPage) },
  { path: 'partida', title: 'Partida — Vertex Chess Arena', loadComponent: () => import('./features/play/play').then((m) => m.PlayPage) },
  { path: 'torneos', title: 'Torneos — Vertex Chess Arena', loadComponent: () => import('./features/tournaments/tournament-list').then((m) => m.TournamentListPage) },
  { path: 'torneos/:id', title: 'Torneo — Vertex Chess Arena', loadComponent: () => import('./features/tournaments/tournament-detail').then((m) => m.TournamentDetailPage) },
  { path: 'historial', title: 'Historial — Vertex Chess Arena', loadComponent: () => import('./features/history/history').then((m) => m.HistoryPage) },
  { path: '**', redirectTo: '' },
];
