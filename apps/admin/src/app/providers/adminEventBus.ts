import { inject, provide, type InjectionKey } from "vue";

export type AdminDomainEvent =
  | { type: "config.changed"; version?: number }
  | { type: "department.changed"; departmentId?: string }
  | { type: "index.changed"; collectionName?: string }
  | { type: "knowledgeBase.changed"; knowledgeBaseId?: string }
  | { type: "user.changed"; userId?: string };

export type AdminDomainEventType = AdminDomainEvent["type"];
export type AdminDomainEventListener<TEvent extends AdminDomainEvent = AdminDomainEvent> = (
  event: TEvent,
) => void;

export interface AdminEventBus {
  emit: (event: AdminDomainEvent) => void;
  off: <TType extends AdminDomainEventType>(
    type: TType,
    listener: AdminDomainEventListener<Extract<AdminDomainEvent, { type: TType }>>,
  ) => void;
  on: <TType extends AdminDomainEventType>(
    type: TType,
    listener: AdminDomainEventListener<Extract<AdminDomainEvent, { type: TType }>>,
  ) => () => void;
}

export function createAdminEventBus(): AdminEventBus {
  const listeners = new Map<AdminDomainEventType, Set<AdminDomainEventListener>>();

  function on<TType extends AdminDomainEventType>(
    type: TType,
    listener: AdminDomainEventListener<Extract<AdminDomainEvent, { type: TType }>>,
  ): () => void {
    const typedListener = listener as AdminDomainEventListener;
    const currentListeners = listeners.get(type) ?? new Set<AdminDomainEventListener>();
    currentListeners.add(typedListener);
    listeners.set(type, currentListeners);
    return () => off(type, listener);
  }

  function off<TType extends AdminDomainEventType>(
    type: TType,
    listener: AdminDomainEventListener<Extract<AdminDomainEvent, { type: TType }>>,
  ): void {
    listeners.get(type)?.delete(listener as AdminDomainEventListener);
  }

  function emit(event: AdminDomainEvent): void {
    listeners.get(event.type)?.forEach((listener) => listener(event));
  }

  return {
    emit,
    off,
    on,
  };
}

const ADMIN_EVENT_BUS_KEY: InjectionKey<AdminEventBus> = Symbol("AdminEventBus");

export function provideAdminEventBus(eventBus: AdminEventBus): void {
  provide(ADMIN_EVENT_BUS_KEY, eventBus);
}

export function useAdminEventBus(): AdminEventBus {
  const eventBus = inject(ADMIN_EVENT_BUS_KEY);
  if (!eventBus) {
    throw new Error("ADMIN_EVENT_BUS_MISSING");
  }
  return eventBus;
}
