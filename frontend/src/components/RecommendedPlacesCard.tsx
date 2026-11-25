"use client";

import { Clock, ExternalLink, MapPin, PlusCircle, Sparkles, Star } from "lucide-react";
import { useState } from "react";

export interface RecommendedPlace {
  name: string;
  category?: string;
  rating?: number;
  address?: string;
  description?: string;
  duration?: string;
  estimatedCost?: string;
  lat?: number;
  lng?: number;
  url?: string;
}

interface RecommendedPlacesCardProps {
  title?: string;
  places: RecommendedPlace[];
  sections?: Array<{ id: number; title: string }>;
  onProposeAdd?: (place: RecommendedPlace, targetSection?: string) => void;
}

export function RecommendedPlacesCard({
  title,
  places,
  sections = [],
  onProposeAdd,
}: RecommendedPlacesCardProps) {
  const [selectedSection, setSelectedSection] = useState<string>(sections[0]?.title || "");

  return (
    <div className="my-2 rounded-2xl border border-slate-800 bg-slate-950/85 p-4 space-y-3 shadow-lg">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-amber-400" />
          <span className="text-sm font-semibold text-slate-100">
            {title || "Recommended Places & Activities"}
          </span>
        </div>
        {sections.length > 0 && (
          <select
            value={selectedSection}
            onChange={(e) => setSelectedSection(e.target.value)}
            className="rounded-lg border border-slate-800 bg-slate-900 px-2 py-1 text-[11px] text-slate-200 focus:outline-none focus:border-indigo-500"
          >
            <option value="">Any day / section</option>
            {sections.map((s) => (
              <option key={s.id} value={s.title}>
                Add to: {s.title}
              </option>
            ))}
          </select>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {places.map((p, idx) => {
          const mapsUrl =
            p.url ||
            `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(
              [p.name, p.address].filter(Boolean).join(", "),
            )}`;

          return (
            <div
              key={idx}
              className="rounded-xl border border-slate-800 bg-slate-900/75 p-3 flex flex-col justify-between gap-2.5 hover:border-slate-700 transition"
            >
              <div className="space-y-1.5">
                <div className="flex items-start justify-between gap-2">
                  <span className="text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full bg-indigo-950 text-indigo-300 border border-indigo-800/60">
                    {p.category || "Place"}
                  </span>
                  {p.rating != null && (
                    <span className="inline-flex items-center gap-1 text-xs font-medium text-amber-300">
                      <Star className="w-3.5 h-3.5 fill-amber-300" />
                      {p.rating.toFixed(1)}
                    </span>
                  )}
                </div>

                <h4 className="text-sm font-semibold text-slate-100 leading-snug">{p.name}</h4>

                {p.address && (
                  <p className="text-[11px] text-slate-400 flex items-center gap-1">
                    <MapPin className="w-3 h-3 shrink-0 text-slate-500" />
                    <span className="line-clamp-1">{p.address}</span>
                  </p>
                )}

                {p.description && <p className="text-xs text-slate-300 leading-relaxed">{p.description}</p>}

                {(p.duration || p.estimatedCost) && (
                  <div className="flex flex-wrap gap-2 pt-0.5 text-[11px] text-slate-400">
                    {p.duration && (
                      <span className="inline-flex items-center gap-1">
                        <Clock className="w-3 h-3" /> {p.duration}
                      </span>
                    )}
                    {p.estimatedCost && <span className="text-emerald-300">{p.estimatedCost}</span>}
                  </div>
                )}
              </div>

              <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between gap-2">
                <a
                  href={mapsUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-xs text-sky-400 hover:text-sky-300"
                >
                  More Info <ExternalLink className="w-3 h-3" />
                </a>

                {onProposeAdd && (
                  <button
                    type="button"
                    onClick={() => onProposeAdd(p, selectedSection || undefined)}
                    className="inline-flex items-center gap-1 text-xs font-medium text-emerald-300 hover:text-emerald-200 bg-emerald-950/60 hover:bg-emerald-900/60 border border-emerald-800/60 px-2.5 py-1 rounded-lg transition cursor-pointer"
                  >
                    <PlusCircle className="w-3.5 h-3.5" /> Add to Trip
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
