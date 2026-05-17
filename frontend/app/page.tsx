"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { ScanDetail, ScanRequest } from "@/lib/types";
import { Header } from "@/components/Header";
import { ScanForm } from "@/components/ScanForm";
import { StatusBar } from "@/components/StatusBar";
import { ResultTable } from "@/components/ResultTable";
import { SkippedList } from "@/components/SkippedList";
import { HistoryPanel } from "@/components/HistoryPanel";

export default function Page() {
  const [cities, setCities] = useState<string[]>([]);
  const [scan, setScan] = useState<ScanDetail | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState<string | undefined>();
  const [historyKey, setHistoryKey] = useState(0);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Load cities + health on mount
  useEffect(() => {
    api
      .cities()
      .then((d) => setCities(d.cities))
      .catch(() => setCities([]));
    api
      .health()
      .then((h) => setVersion(h.version))
      .catch(() => {});
  }, []);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const startPolling = useCallback(
    (scanId: string) => {
      stopPolling();
      pollRef.current = setInterval(async () => {
        try {
          const d = await api.getScan(scanId);
          setScan(d);
          if (d.status === "done" || d.status === "error") {
            stopPolling();
            setRunning(false);
            setHistoryKey((k) => k + 1);
          }
        } catch (e) {
          stopPolling();
          setRunning(false);
          setError(String(e));
        }
      }, 1000);
    },
    [stopPolling],
  );

  const handleSubmit = useCallback(
    async (req: ScanRequest) => {
      setError(null);
      setRunning(true);
      try {
        const { scan_id } = await api.createScan(req);
        const initial = await api.getScan(scan_id);
        setScan(initial);
        startPolling(scan_id);
      } catch (e) {
        setRunning(false);
        setError(String(e));
      }
    },
    [startPolling],
  );

  const handleHistorySelect = useCallback(
    async (scanId: string) => {
      stopPolling();
      setRunning(false);
      try {
        const d = await api.getScan(scanId);
        setScan(d);
      } catch (e) {
        setError(String(e));
      }
    },
    [stopPolling],
  );

  useEffect(() => () => stopPolling(), [stopPolling]);

  return (
    <div className="min-h-screen">
      <Header version={version} />
      <main className="mx-auto max-w-6xl px-4 py-6">
        {error && (
          <div className="mb-4 rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
            {error}
          </div>
        )}
        <div className="grid grid-cols-1 gap-6 md:grid-cols-[320px_1fr]">
          <aside>
            <ScanForm
              cities={cities.length ? cities : ["Tel Aviv", "Ramat Gan", "Haifa", "Jerusalem"]}
              disabled={running}
              onSubmit={handleSubmit}
            />
          </aside>
          <section className="space-y-4">
            <StatusBar scan={scan} />
            {scan && scan.status === "done" && (
              <>
                <ResultTable results={scan.results} />
                <SkippedList items={scan.skipped} />
              </>
            )}
            <HistoryPanel onSelect={handleHistorySelect} refreshKey={historyKey} />
          </section>
        </div>
        <footer className="mt-10 text-center text-xs text-slate-400">
          Built locally · No cloud · No tracking
        </footer>
      </main>
    </div>
  );
}
