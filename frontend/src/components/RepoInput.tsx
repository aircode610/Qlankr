import { useState } from 'react';
import { Loader2 } from '@/lib/lucide-icons';

interface RepoInputProps {
  onIndex: (repoUrl: string) => void;
  indexing: boolean;
  indexed: boolean;
  indexMessages: Array<{ stage: string; summary: string }>;
}

export const RepoInput = ({ onIndex, indexing, indexed, indexMessages }: RepoInputProps) => {
  const [url, setUrl] = useState('');

  return (
    <div className="flex flex-col gap-3">
      <h3 className="text-xs font-medium tracking-wide text-text-secondary uppercase">Repository</h3>
      <div className="flex gap-2">
        <input
          type="text"
          placeholder="https://github.com/owner/repo"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          disabled={indexing}
          className="flex-1 rounded border border-border-subtle bg-elevated px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none disabled:opacity-50"
        />
        <button
          onClick={() => onIndex(url)}
          disabled={indexing || !url.trim()}
          className="rounded bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-dim disabled:opacity-50"
        >
          {indexing ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Index'}
        </button>
      </div>

      {indexed && (
        <div className="flex items-center gap-2 rounded border border-emerald-500/30 bg-emerald-500/10 px-3 py-1.5 text-xs text-emerald-400">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
          Indexed
        </div>
      )}

      {indexMessages.length > 0 && (
        <div className="scrollbar-thin max-h-32 overflow-y-auto rounded border border-border-subtle bg-deep p-2">
          {indexMessages.map((msg, i) => (
            <div key={i} className="flex gap-2 py-0.5 text-[11px]">
              <span className="shrink-0 text-accent">{msg.stage}</span>
              <span className="text-text-muted">{msg.summary}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
