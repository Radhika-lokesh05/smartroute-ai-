import React, { useState } from 'react';
import { Download, Loader2 } from 'lucide-react';
import { downloadMetricsCsv } from '@/api/admin';

interface CsvExportButtonsProps {
  days: number;
  origin: string;
}

export const CsvExportButtons: React.FC<CsvExportButtonsProps> = ({ days, origin }) => {
  const [downloadingInc, setDownloadingInc] = useState(false);
  const [downloadingDisp, setDownloadingDisp] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleDownload = async (kind: 'incidents' | 'dispatches') => {
    setError(null);
    if (kind === 'incidents') setDownloadingInc(true);
    else setDownloadingDisp(true);

    try {
      await downloadMetricsCsv(kind, days, origin);
    } catch (err: any) {
      setError(err?.message || 'Download failed');
    } finally {
      if (kind === 'incidents') setDownloadingInc(false);
      else setDownloadingDisp(false);
    }
  };

  return (
    <div className="flex items-center gap-2">
      {error && <span className="text-xs text-red-400 font-mono">{error}</span>}
      <button
        type="button"
        data-testid="export-incidents-btn"
        disabled={downloadingInc}
        onClick={() => handleDownload('incidents')}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-medium transition disabled:opacity-50"
      >
        {downloadingInc ? <Loader2 className="w-3.5 h-3.5 animate-spin text-cyan-400" /> : <Download className="w-3.5 h-3.5" />}
        <span>Incidents CSV</span>
      </button>

      <button
        type="button"
        data-testid="export-dispatches-btn"
        disabled={downloadingDisp}
        onClick={() => handleDownload('dispatches')}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-medium transition disabled:opacity-50"
      >
        {downloadingDisp ? <Loader2 className="w-3.5 h-3.5 animate-spin text-purple-400" /> : <Download className="w-3.5 h-3.5" />}
        <span>Dispatches CSV</span>
      </button>
    </div>
  );
};
