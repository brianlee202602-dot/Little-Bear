import type { PaginationData } from "@/api/commonTypes";

export type PaginationState = {
  page: number;
  pageSize: number;
  total: number;
};

export function syncPaginationState(state: PaginationState, pagination: PaginationData): void {
  state.page = pagination.page;
  state.pageSize = pagination.page_size;
  state.total = pagination.total;
}

export function clearPaginationState(state: PaginationState): void {
  state.page = 1;
  state.total = 0;
}

export function paginationTotalPages(state: PaginationState): number {
  return Math.max(1, Math.ceil(state.total / Math.max(state.pageSize, 1)));
}

export function paginationStart(state: PaginationState): number {
  if (state.total === 0) {
    return 0;
  }
  return (state.page - 1) * state.pageSize + 1;
}

export function paginationEnd(state: PaginationState): number {
  return Math.min(state.total, state.page * state.pageSize);
}

export function changePaginationPage(
  state: PaginationState,
  refresh: () => Promise<void>,
  page: number,
): void {
  const nextPage = Math.min(Math.max(page, 1), paginationTotalPages(state));
  if (state.page === nextPage) {
    return;
  }
  state.page = nextPage;
  void refresh();
}

export function changePaginationPageSize(
  state: PaginationState,
  refresh: () => Promise<void>,
  pageSize?: number,
): void {
  if (typeof pageSize === "number") {
    state.pageSize = pageSize;
  }
  state.page = 1;
  void refresh();
}

export function refreshFirstPage(state: PaginationState, refresh: () => Promise<void>): void {
  state.page = 1;
  void refresh();
}
