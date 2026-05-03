import React from "react";
import { Link } from "react-router-dom";
import { BookOpen, Settings } from "lucide-react";
import { useJarvisHeaderSnapshot } from "./DashboardCards";

export const JarvisTopBar: React.FC = () => {
  const snapshot = useJarvisHeaderSnapshot();

  return (
    <header className="border-b border-slate-200/80 bg-white/90 backdrop-blur">
      <div className="grid gap-3 px-4 py-3 lg:grid-cols-[minmax(160px,200px)_1px_minmax(160px,1fr)_minmax(100px,130px)_minmax(110px,140px)_minmax(160px,auto)] lg:items-center">
        <div className="flex min-w-0 items-center gap-2.5">
          <div className="flex h-12 w-12 items-center justify-center rounded-[18px] bg-[radial-gradient(circle_at_top,#8b5cf6,transparent_55%),linear-gradient(135deg,#eef2ff,#dbeafe)] text-2xl shadow-sm shadow-indigo-200/70">
            🤖
          </div>
          <div className="min-w-0">
            <div className="truncate text-[1.25rem] font-semibold tracking-tight text-slate-900">
              Jarvis-Life
            </div>
            <div className="mt-0.5 text-[0.82rem] text-slate-500">
              你的智能生活管家
            </div>
          </div>
        </div>

        <div className="hidden h-10 w-px justify-self-center rounded-full bg-slate-200 lg:block" />

        <div className="min-w-0">
          <div className="truncate text-[1.28rem] font-semibold tracking-tight text-slate-950">
            {snapshot.greeting}
          </div>
          <div className="mt-1 truncate text-[0.85rem] text-slate-500">
            {snapshot.subtitle}
          </div>
        </div>

        <div className="text-center lg:text-left">
          <div className="text-[1.45rem] font-semibold tracking-tight text-slate-950">
            {snapshot.timeLabel}
          </div>
          <div className="mt-1 text-[0.8rem] text-slate-500">{snapshot.dateLabel}</div>
        </div>

        <div className="flex items-center gap-2 px-1 py-1">
          <span className="text-[1.6rem]">{snapshot.weatherIcon}</span>
          <div className="min-w-0">
            <div className="text-[1rem] font-semibold text-slate-900">
              {snapshot.temperatureLabel}
            </div>
            <div className="truncate text-[0.72rem] text-slate-500">
              {snapshot.weatherLabel}
            </div>
            <div className="truncate text-[0.72rem] text-slate-400">
              {snapshot.locationLabel}
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-end gap-2 lg:gap-2.5">
          <Link
            to="/knowledge"
            className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:text-slate-900"
          >
            <BookOpen size={16} />
            知识库
          </Link>

          <Link
            to="/settings"
            className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:text-slate-900"
          >
            <Settings size={16} />
            设置
          </Link>
        </div>
      </div>
    </header>
  );
};
