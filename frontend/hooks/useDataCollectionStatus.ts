"use client";

import { useEffect, useRef, useState } from "react";
import { liveRunSocketUrl } from "@/lib/api";
import type { LiveRunStatusMessage } from "@/lib/types";

export interface DataCollectionStatus {
  phase: string;
  itemCount: number;
  messages: LiveRunStatusMessage[];
}

const INITIAL: DataCollectionStatus = { phase: "idle", itemCount: 0, messages: [] };

// Backs app/brands/[id]/live-run/page.tsx -- subscribes to api/websocket.py's
// /ws/live-run/{brand_id}/status, which relays workers/data_collection.py's
// per-source phase broadcasts over Redis pub/sub (infra/pubsub.py). apiKey
// may be empty -- liveRunSocketUrl substitutes a dev-only default (see
// lib/api.ts); the endpoint still closes an unauthorized socket immediately
// (4003) whenever SMM_AUTH_DEV_BYPASS is off.
export function useDataCollectionStatus(brandId: string, apiKey = ""): DataCollectionStatus {
  const [status, setStatus] = useState<DataCollectionStatus>(INITIAL);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!brandId) return;

    setStatus(INITIAL);
    const ws = new WebSocket(liveRunSocketUrl(brandId, apiKey));
    socketRef.current = ws;

    ws.onmessage = (event) => {
      const update = JSON.parse(event.data) as LiveRunStatusMessage;
      setStatus((prev) => ({
        phase: update.phase,
        itemCount: update.item_count,
        messages: [...prev.messages, update],
      }));
    };

    return () => {
      ws.close();
      socketRef.current = null;
    };
  }, [brandId, apiKey]);

  return status;
}
