// shadowlink-web/src/pages/JarvisPage.tsx
import React, { useEffect } from "react";
import { JarvisHome } from "@/components/jarvis/JarvisHome";
import { JarvisTopBar } from "@/components/jarvis/JarvisTopBar";
import { useJarvisStore } from "@/stores/jarvisStore";
import { jarvisApi } from "@/services/jarvisApi";

/**
 * JarvisPage — Jarvis · Be IronMan. Full-viewport command center.
 *
 * Top-level wrapper: subscribes to proactive SSE stream, loads context + agents,
 * and renders JarvisTopBar + JarvisHome. All interaction state lives in the store.
 */
export const JarvisPage: React.FC = () => {
  const loadContext = useJarvisStore((s) => s.loadContext);
  const loadAgents = useJarvisStore((s) => s.loadAgents);
  const loadProactiveMessages = useJarvisStore((s) => s.loadProactiveMessages);
  const addProactiveMessage = useJarvisStore((s) => s.addProactiveMessage);

  useEffect(() => {
    loadContext();
    loadAgents();
    loadProactiveMessages();
    const unsubscribe = jarvisApi.subscribeToMessages(addProactiveMessage);
    return unsubscribe;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div
      className="h-screen w-screen flex flex-col overflow-hidden"
      style={{
        backgroundColor: "var(--color-background, #f9fafb)",
        color: "var(--color-text, #1f2937)",
      }}
    >
      <JarvisTopBar />
      <JarvisHome />
    </div>
  );
};
