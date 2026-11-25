"use client";

import { Building2, Calendar, CheckCircle2, ExternalLink, MapPin, Phone, Star, Ticket, User, Wallet } from "lucide-react";

export interface BookedHotelData {
  name: string;
  address?: string;
  checkIn?: string;
  checkOut?: string;
  nights?: number;
  confirmationNumber?: string;
  bookedUnder?: string;
  cost?: string;
  rating?: number;
  reviewCount?: number;
  phone?: string;
  provider?: string;
  url?: string;
  notes?: string;
}

export function BookedHotelCard({ data }: { data: BookedHotelData }) {
  const mapsUrl =
    data.url ||
    `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(
      [data.name, data.address].filter(Boolean).join(", "),
    )}`;

  return (
    <div className="my-2 rounded-2xl border border-slate-800 bg-slate-950/90 p-4 space-y-3 shadow-lg">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full bg-emerald-950 text-emerald-300 border border-emerald-800/60">
              <CheckCircle2 className="w-3 h-3" /> {data.provider || "Booked Lodging"}
            </span>
            {data.rating != null && (
              <span className="inline-flex items-center gap-1 text-xs font-medium text-amber-300">
                <Star className="w-3.5 h-3.5 fill-amber-300" />
                {data.rating.toFixed(1)}
                {data.reviewCount != null && <span className="text-slate-400">({data.reviewCount})</span>}
              </span>
            )}
          </div>
          <h3 className="text-base font-semibold text-slate-100 flex items-center gap-2">
            <Building2 className="w-4 h-4 text-sky-400 shrink-0" />
            <span>{data.name}</span>
          </h3>
        </div>

        <a
          href={mapsUrl}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 text-xs font-medium text-sky-300 hover:text-sky-200 bg-sky-950/60 hover:bg-sky-900/60 border border-sky-800/60 px-2.5 py-1.5 rounded-xl transition shrink-0"
        >
          Open Map <ExternalLink className="w-3 h-3" />
        </a>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 text-xs">
        {data.address && (
          <div className="flex items-start gap-2 rounded-xl bg-slate-900/70 border border-slate-800/80 p-2.5 sm:col-span-2">
            <MapPin className="w-3.5 h-3.5 text-rose-400 shrink-0 mt-0.5" />
            <span className="text-slate-300">{data.address}</span>
          </div>
        )}

        {(data.checkIn || data.checkOut) && (
          <div className="flex items-start gap-2 rounded-xl bg-slate-900/70 border border-slate-800/80 p-2.5">
            <Calendar className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
            <div className="text-slate-300">
              <div className="text-[11px] text-slate-400">Dates{data.nights ? ` (${data.nights} nights)` : ""}</div>
              <div>
                {data.checkIn || "?"} → {data.checkOut || "?"}
              </div>
            </div>
          </div>
        )}

        {data.cost && (
          <div className="flex items-start gap-2 rounded-xl bg-slate-900/70 border border-slate-800/80 p-2.5">
            <Wallet className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
            <div className="text-slate-300">
              <div className="text-[11px] text-slate-400">Cost</div>
              <div className="font-medium text-emerald-300">{data.cost}</div>
            </div>
          </div>
        )}

        {data.confirmationNumber && (
          <div className="flex items-start gap-2 rounded-xl bg-slate-900/70 border border-slate-800/80 p-2.5">
            <Ticket className="w-3.5 h-3.5 text-indigo-400 shrink-0 mt-0.5" />
            <div className="text-slate-300">
              <div className="text-[11px] text-slate-400">Confirmation #</div>
              <div className="font-mono">{data.confirmationNumber}</div>
            </div>
          </div>
        )}

        {data.bookedUnder && (
          <div className="flex items-start gap-2 rounded-xl bg-slate-900/70 border border-slate-800/80 p-2.5">
            <User className="w-3.5 h-3.5 text-violet-400 shrink-0 mt-0.5" />
            <div className="text-slate-300">
              <div className="text-[11px] text-slate-400">Booked Under</div>
              <div>{data.bookedUnder}</div>
            </div>
          </div>
        )}

        {data.phone && (
          <div className="flex items-start gap-2 rounded-xl bg-slate-900/70 border border-slate-800/80 p-2.5 sm:col-span-2">
            <Phone className="w-3.5 h-3.5 text-sky-400 shrink-0 mt-0.5" />
            <a href={`tel:${data.phone}`} className="text-sky-300 hover:underline">
              {data.phone}
            </a>
          </div>
        )}
      </div>

      {data.notes && <p className="text-xs text-slate-400 border-t border-slate-800/80 pt-2">{data.notes}</p>}
    </div>
  );
}
