"use client";

import { Building2, ExternalLink, PlusCircle, Star } from "lucide-react";

interface HotelItem {
  name: string;
  hotel_id?: string;
  rating?: number | null;
  review_count?: number | null;
  price_text?: string | null;
  price_per_night?: number | null;
  total_price?: number | null;
  currency?: string;
  genius_price?: number | null;
  genius_price_text?: string | null;
  is_genius_deal?: boolean;
  vip_price?: number | null;
  is_vip_deal?: boolean;
  address?: string | null;
  url?: string | null;
  badges?: string[];
  provider?: string;
  check_in?: string;
  check_out?: string;
}

interface HotelSection {
  provider?: string;
  count?: number;
  hotels?: HotelItem[];
  error?: string;
}

interface HotelComparisonProps {
  toolName: string;
  data: {
    location?: string;
    check_in?: string;
    check_out?: string;
    currency?: string;
    booking?: HotelSection;
    agoda?: HotelSection;
    provider?: string;
    hotels?: HotelItem[];
  };
  onProposeHotel?: (hotel: HotelItem, checkIn?: string, checkOut?: string) => void;
}

function HotelCard({
  hotel,
  providerLabel,
  accentClass,
  checkIn,
  checkOut,
  onPropose,
}: {
  hotel: HotelItem;
  providerLabel: string;
  accentClass: string;
  checkIn?: string;
  checkOut?: string;
  onPropose?: (h: HotelItem, ci?: string, co?: string) => void;
}) {
  const effectivePrice =
    hotel.genius_price_text ||
    hotel.price_text ||
    (hotel.genius_price != null
      ? `${hotel.currency || "EUR"} ${hotel.genius_price.toFixed(0)}/night`
      : hotel.vip_price != null
        ? `${hotel.currency || "EUR"} ${hotel.vip_price.toFixed(0)}/night`
        : hotel.price_per_night != null
          ? `${hotel.currency || "EUR"} ${hotel.price_per_night.toFixed(0)}/night`
          : "Price on site");

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-3 flex flex-col justify-between gap-2 hover:border-slate-700 transition">
      <div>
        <div className="flex items-start justify-between gap-2">
          <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${accentClass}`}>
            {providerLabel}
          </span>
          {hotel.rating != null && (
            <span className="inline-flex items-center gap-1 text-xs font-medium text-amber-300">
              <Star className="w-3.5 h-3.5 fill-amber-300" />
              {hotel.rating.toFixed(1)}
            </span>
          )}
        </div>
        <h4 className="mt-2 text-sm font-semibold text-slate-100 leading-snug">{hotel.name}</h4>
        {hotel.address && <p className="text-xs text-slate-400 mt-0.5 line-clamp-1">{hotel.address}</p>}
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-base font-bold text-emerald-400">{effectivePrice}</span>
          {(hotel.is_genius_deal || hotel.is_vip_deal) && (
            <span className="text-[11px] text-emerald-300/90 bg-emerald-950/70 border border-emerald-800/60 px-1.5 py-0.5 rounded">
              {hotel.is_genius_deal ? "Genius Deal" : "AgodaVIP"}
            </span>
          )}
        </div>
        {hotel.badges && hotel.badges.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {hotel.badges.slice(0, 3).map((b, i) => (
              <span key={i} className="text-[10px] text-slate-300 bg-slate-800 px-1.5 py-0.5 rounded">
                {b}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between gap-2">
        {hotel.url ? (
          <a
            href={hotel.url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-xs text-sky-400 hover:text-sky-300"
          >
            View Deal <ExternalLink className="w-3 h-3" />
          </a>
        ) : (
          <span />
        )}
        {onPropose && (
          <button
            type="button"
            onClick={() => onPropose(hotel, hotel.check_in || checkIn, hotel.check_out || checkOut)}
            className="inline-flex items-center gap-1 text-xs font-medium text-indigo-300 hover:text-indigo-200 bg-indigo-950/60 hover:bg-indigo-900/60 border border-indigo-800/60 px-2 py-1 rounded-lg transition cursor-pointer"
          >
            <PlusCircle className="w-3.5 h-3.5" /> Add to Trip
          </button>
        )}
      </div>
    </div>
  );
}

export function HotelComparisonCard({ toolName, data, onProposeHotel }: HotelComparisonProps) {
  const isDual = toolName === "search_hotels_dual_ota";
  const bookingHotels = isDual
    ? data.booking?.hotels || []
    : toolName === "booking_search_hotels"
      ? data.hotels || []
      : [];
  const agodaHotels = isDual
    ? data.agoda?.hotels || []
    : toolName === "agoda_search_hotels"
      ? data.hotels || []
      : [];

  return (
    <div className="my-2 rounded-2xl border border-slate-800 bg-slate-950/80 p-4 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Building2 className="w-4 h-4 text-sky-400" />
          <span className="text-sm font-semibold text-slate-100">
            Hotels{data.location ? ` in ${data.location}` : ""}
          </span>
        </div>
        {data.check_in && data.check_out && (
          <span className="text-xs text-slate-400">
            {data.check_in} → {data.check_out}
          </span>
        )}
      </div>

      {data.booking?.error && (
        <div className="text-xs text-amber-300 bg-amber-950/40 border border-amber-800/50 rounded-lg p-2">
          Booking.com: {data.booking.error}
        </div>
      )}
      {data.agoda?.error && (
        <div className="text-xs text-amber-300 bg-amber-950/40 border border-amber-800/50 rounded-lg p-2">
          Agoda: {data.agoda.error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {bookingHotels.slice(0, 4).map((h, idx) => (
          <HotelCard
            key={`b-${idx}`}
            hotel={h}
            providerLabel="Booking.com"
            accentClass="bg-blue-950 text-blue-300 border border-blue-800/60"
            checkIn={data.check_in}
            checkOut={data.check_out}
            onPropose={onProposeHotel}
          />
        ))}
        {agodaHotels.slice(0, 4).map((h, idx) => (
          <HotelCard
            key={`a-${idx}`}
            hotel={h}
            providerLabel="Agoda"
            accentClass="bg-rose-950 text-rose-300 border border-rose-800/60"
            checkIn={data.check_in}
            checkOut={data.check_out}
            onPropose={onProposeHotel}
          />
        ))}
      </div>
    </div>
  );
}
