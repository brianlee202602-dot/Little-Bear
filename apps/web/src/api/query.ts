import {
  ApiRequestError,
  isApiErrorPayload,
  parseJson,
  requestJson,
  requestRaw,
} from "./http";
import type {
  CitationData,
  QueryConfidence,
  QueryRequest,
  QueryResponse,
  QueryStreamDone,
  QueryStreamHandlers,
  QueryStreamMetadata,
} from "./types";

export type {
  CitationData,
  QueryConfidence,
  QueryHistoryMessage,
  QueryMode,
  QueryRequest,
  QueryResponse,
  QueryStreamDone,
  QueryStreamHandlers,
  QueryStreamMetadata,
} from "./types";

export async function createQuery(
  payload: QueryRequest,
  accessToken: string,
): Promise<QueryResponse> {
  return requestJson<QueryResponse>(
    "/internal/v1/queries",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    accessToken,
  );
}

export async function streamQuery(
  payload: QueryRequest,
  accessToken: string,
  handlers: QueryStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const headers = new Headers({
    accept: "text/event-stream",
    "content-type": "application/json",
  });
  if (accessToken) {
    headers.set("authorization", `Bearer ${accessToken}`);
  }
  const response = await requestRaw("/internal/v1/query-streams", {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
    signal,
  });

  if (!response.ok) {
    const payload = parseJson(await response.text());
    throw new ApiRequestError(
      response.status,
      isApiErrorPayload(payload) ? payload : null,
      `请求失败，状态码 ${response.status}`,
    );
  }
  if (!response.body) {
    throw new ApiRequestError(0, null, "浏览器不支持流式响应");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    buffer = dispatchBufferedEvents(buffer, handlers);
  }
  buffer += decoder.decode();
  dispatchBufferedEvents(`${buffer}\n\n`, handlers);
}

function dispatchBufferedEvents(buffer: string, handlers: QueryStreamHandlers): string {
  const parts = buffer.split("\n\n");
  const tail = parts.pop() ?? "";
  for (const frame of parts) {
    dispatchEventFrame(frame, handlers);
  }
  return tail;
}

function dispatchEventFrame(frame: string, handlers: QueryStreamHandlers): void {
  let eventName = "message";
  const dataLines: string[] = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) {
      eventName = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trimStart());
    }
  }
  const payload = parseJson(dataLines.join("\n"));
  if (!payload || typeof payload !== "object") {
    return;
  }
  if (eventName === "metadata") {
    if (!isQueryStreamMetadata(payload)) {
      throw new ApiRequestError(0, null, "流式查询 metadata 事件格式无效");
    }
    handlers.onMetadata?.(payload);
  } else if (eventName === "token") {
    if (!isRecord(payload) || typeof payload.delta !== "string") {
      throw new ApiRequestError(0, null, "流式查询 token 事件格式无效");
    }
    handlers.onToken?.(payload.delta);
  } else if (eventName === "citation") {
    if (!isCitationData(payload)) {
      throw new ApiRequestError(0, null, "流式查询 citation 事件格式无效");
    }
    handlers.onCitation?.(payload);
  } else if (eventName === "done") {
    if (!isQueryStreamDone(payload)) {
      throw new ApiRequestError(0, null, "流式查询 done 事件格式无效");
    }
    handlers.onDone?.(payload);
  } else if (eventName === "error") {
    if (!isApiErrorPayload(payload)) {
      throw new ApiRequestError(0, null, "流式查询失败");
    }
    throw new ApiRequestError(0, payload, "流式查询失败");
  }
}

function isQueryStreamMetadata(value: unknown): value is QueryStreamMetadata {
  return (
    isRecord(value) &&
    typeof value.debug_id === "string" &&
    isNullableString(value.conversation_id) &&
    isNullableString(value.message_id) &&
    isQueryConfidence(value.confidence) &&
    typeof value.degraded === "boolean" &&
    isNullableString(value.degrade_reason) &&
    (value.streaming === undefined || typeof value.streaming === "boolean")
  );
}

function isQueryStreamDone(value: unknown): value is QueryStreamDone {
  return (
    isRecord(value) &&
    typeof value.debug_id === "string" &&
    isNullableString(value.conversation_id) &&
    isNullableString(value.message_id) &&
    typeof value.answer === "string" &&
    Array.isArray(value.citations) &&
    value.citations.every(isCitationData) &&
    isQueryConfidence(value.confidence) &&
    typeof value.degraded === "boolean" &&
    isNullableString(value.degrade_reason)
  );
}

function isCitationData(value: unknown): value is CitationData {
  return (
    isRecord(value) &&
    typeof value.source_id === "string" &&
    typeof value.doc_id === "string" &&
    typeof value.document_version_id === "string" &&
    typeof value.title === "string" &&
    typeof value.page_start === "number" &&
    typeof value.page_end === "number" &&
    typeof value.score === "number"
  );
}

function isQueryConfidence(value: unknown): value is QueryConfidence {
  return value === "low" || value === "medium" || value === "high";
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object";
}
