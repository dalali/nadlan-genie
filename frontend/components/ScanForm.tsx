"use client";

import { useState } from "react";
import type { ScanRequest } from "@/lib/types";

interface Props {
  cities: string[];
  disabled?: boolean;
  onSubmit: (req: ScanRequest) => void;
}

const PROPERTY_TYPES: ScanRequest["property_type"][] = [
  "apartment",
  "garden_apartment",
  "penthouse",
  "private_house",
];

export function ScanForm({ cities, disabled, onSubmit }: Props) {
  const [city, setCity] = useState(cities[0] || "Tel Aviv");
  const [roomsMin, setRoomsMin] = useState(3);
  const [roomsMax, setRoomsMax] = useState(4);
  const [priceMax, setPriceMax] = useState(3_000_000);
  const [discount, setDiscount] = useState(15);
  const [maxPages, setMaxPages] = useState(3);
  const [propertyType, setPropertyType] =
    useState<ScanRequest["property_type"]>("apartment");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit({
      city,
      rooms_min: roomsMin,
      rooms_max: roomsMax,
      price_max: priceMax,
      discount_threshold: discount / 100,
      max_pages: maxPages,
      property_type: propertyType,
    });
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
    >
      <h2 className="text-lg font-semibold">Scan</h2>

      <label className="block text-sm">
        <span className="text-slate-600">City</span>
        <select
          className="mt-1 block w-full rounded border-slate-300 bg-white text-sm"
          value={city}
          onChange={(e) => setCity(e.target.value)}
        >
          {cities.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </label>

      <div className="grid grid-cols-2 gap-3">
        <label className="block text-sm">
          <span className="text-slate-600">Rooms min</span>
          <input
            type="number"
            min={1}
            max={10}
            step={0.5}
            value={roomsMin}
            onChange={(e) => setRoomsMin(Number(e.target.value))}
            className="mt-1 block w-full rounded border-slate-300 text-sm tabular-nums"
          />
        </label>
        <label className="block text-sm">
          <span className="text-slate-600">Rooms max</span>
          <input
            type="number"
            min={1}
            max={10}
            step={0.5}
            value={roomsMax}
            onChange={(e) => setRoomsMax(Number(e.target.value))}
            className="mt-1 block w-full rounded border-slate-300 text-sm tabular-nums"
          />
        </label>
      </div>

      <label className="block text-sm">
        <span className="text-slate-600">Max price (₪)</span>
        <input
          type="number"
          min={1}
          step={50000}
          value={priceMax}
          onChange={(e) => setPriceMax(Number(e.target.value))}
          className="mt-1 block w-full rounded border-slate-300 text-sm tabular-nums"
        />
      </label>

      <label className="block text-sm">
        <span className="text-slate-600">
          Discount threshold: <span className="tabular-nums">{discount}%</span>
        </span>
        <input
          type="range"
          min={0}
          max={50}
          step={1}
          value={discount}
          onChange={(e) => setDiscount(Number(e.target.value))}
          className="mt-1 block w-full"
        />
      </label>

      <div className="grid grid-cols-2 gap-3">
        <label className="block text-sm">
          <span className="text-slate-600">Max pages</span>
          <input
            type="number"
            min={1}
            max={3}
            value={maxPages}
            onChange={(e) => setMaxPages(Number(e.target.value))}
            className="mt-1 block w-full rounded border-slate-300 text-sm tabular-nums"
          />
        </label>
        <label className="block text-sm">
          <span className="text-slate-600">Type</span>
          <select
            className="mt-1 block w-full rounded border-slate-300 bg-white text-sm"
            value={propertyType}
            onChange={(e) =>
              setPropertyType(e.target.value as ScanRequest["property_type"])
            }
          >
            {PROPERTY_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
      </div>

      <button
        type="submit"
        disabled={disabled}
        className="w-full rounded bg-emerald-600 px-3 py-2 text-sm font-medium text-white shadow-sm hover:bg-emerald-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-600 disabled:cursor-not-allowed disabled:bg-slate-300"
      >
        {disabled ? "Scanning..." : "Scan Now"}
      </button>
    </form>
  );
}
