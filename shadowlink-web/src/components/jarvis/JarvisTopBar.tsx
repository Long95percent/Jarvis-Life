import React from "react";
import { Link } from "react-router-dom";
import { BookOpen, Settings } from "lucide-react";
import { useJarvisHeaderSnapshot } from "./DashboardCards";

export const JarvisTopBar: React.FC = () => {
  const snapshot = useJarvisHeaderSnapshot();

  return (
    <header className="border-b border-slate-200/80 bg-white/90 backdrop-blur">
      <div className="grid gap-4 px-5 py-4 lg:grid-cols-[220px_1px_minmax(240px,1fr)_140px_150px_auto] lg:items-center">
        <div className="flex items-center gap-3">
          <div className="flex h-14 w-14 items-center justify-center rounded-[20px] bg-[radial-gradient(circle_at_top,#8b5cf6,transparent_55%),linear-gradient(135deg,#eef2ff,#dbeafe)] text-3xl shadow-sm shadow-indigo-200/70">
            🤖
          </div>
          <div className="min-w-0">
            <div className="truncate text-[1.55rem] font-semibold tracking-tight text-slate-900">
              Jarvis-Life
            </div>
            <div className="mt-0.5 text-sm text-slate-500">
              你的智能生活管家
            </div>
          </div>
        </div>

        <div className="hidden h-12 w-px justify-self-center rounded-full bg-slate-200 lg:block" />

        <div className="min-w-0">
          <div className="truncate text-[1.75rem] font-semibold tracking-tight text-slate-950">
            {snapshot.greeting}
          </div>
          <div className="mt-1 truncate text-sm text-slate-500">
            {snapshot.subtitle}
          </div>
        </div>

        <div className="text-center lg:text-left">
          <div className="text-[1.95rem] font-semibold tracking-tight text-slate-950">
            {snapshot.timeLabel}
          </div>
          <div className="mt-1 text-[0.95rem] text-slate-500">{snapshot.dateLabel}</div>
        </div>

        <div className="flex items-center gap-2.5 px-1 py-1">
          <span className="text-[2rem]">{snapshot.weatherIcon}</span>
          <div className="min-w-0">
            <div className="text-xl font-semibold text-slate-900">
              {snapshot.temperatureLabel}
            </div>
            <div className="truncate text-xs text-slate-500">
              {snapshot.weatherLabel}
            </div>
            <div className="truncate text-xs text-slate-400">
              {snapshot.locationLabel}
            </div>
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 lg:gap-3">
          <Link
            to="/knowledge"
            className="inline-flex items-center gap-2.5 rounded-2xl border border-slate-200 bg-white px-5 py-3.5 text-base font-medium text-slate-700 transition hover:border-slate-300 hover:text-slate-900"
          >
            <BookOpen size={19} />
            知识库
          </Link>

          <Link
            to="/settings"
            className="inline-flex items-center gap-2.5 rounded-2xl border border-slate-200 bg-white px-5 py-3.5 text-base font-medium text-slate-700 transition hover:border-slate-300 hover:text-slate-900"
          >
            <Settings size={19} />
            设置
          </Link>
        </div>
      </div>
    </header>
  );
};
