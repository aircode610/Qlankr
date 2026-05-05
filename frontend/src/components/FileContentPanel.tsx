import { useState, useEffect, useCallback } from 'react';
import { X, Copy, CheckCircle, Loader2, FileCode } from '@/lib/lucide-icons';
import { getFileContent } from '../services/api';

interface FileContentPanelProps {
  filePath: string;
  repoName: string | null;
  onClose: () => void;
}

export const FileContentPanel = ({ filePath, repoName, onClose }: FileContentPanelProps) => {
  const [content, setContent] = useState<string | null>(null);
  const [language, setLanguage] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!repoName || !filePath) return;
    setLoading(true);
    setError(null);
    setContent(null);

    const [owner, repo] = repoName.split('/');
    if (!owner || !repo) {
      setError('Invalid repo name');
      setLoading(false);
      return;
    }

    getFileContent(owner, repo, filePath)
      .then((data) => {
        setContent(data.content);
        setLanguage(data.language);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [filePath, repoName]);

  const handleCopy = useCallback(() => {
    if (!content) return;
    navigator.clipboard.writeText(content).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }, [content]);

  const fileName = filePath.split('/').pop() || filePath;
  const lines = content?.split('\n') ?? [];

  return (
    <div className="flex h-full w-[420px] flex-col border-l border-border-subtle bg-surface animate-slide-in">
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-border-subtle px-3 py-2">
        <FileCode className="h-3.5 w-3.5 shrink-0 text-accent" />
        <div className="min-w-0 flex-1">
          <p className="truncate font-mono text-xs font-medium text-text-primary" title={filePath}>
            {fileName}
          </p>
          <p className="truncate text-[10px] text-text-muted" title={filePath}>
            {filePath}
          </p>
        </div>
        {language && (
          <span className="shrink-0 rounded border border-border-subtle bg-elevated px-1.5 py-0.5 text-[10px] text-text-muted">
            {language}
          </span>
        )}
        <button
          onClick={handleCopy}
          className="shrink-0 rounded p-1 text-text-muted transition-colors hover:bg-hover hover:text-text-primary"
          title="Copy file content"
        >
          {copied ? <CheckCircle className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
        </button>
        <button
          onClick={onClose}
          className="shrink-0 rounded p-1 text-text-muted transition-colors hover:bg-hover hover:text-text-primary"
          title="Close"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Content */}
      <div className="scrollbar-thin flex-1 overflow-auto bg-deep">
        {loading && (
          <div className="flex h-full items-center justify-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin text-accent" />
            <span className="text-xs text-text-muted">Loading file...</span>
          </div>
        )}

        {error && (
          <div className="flex h-full flex-col items-center justify-center gap-2 p-4">
            <p className="text-xs text-red-400">Failed to load file</p>
            <p className="text-[11px] text-text-muted">{error}</p>
          </div>
        )}

        {content !== null && !loading && (
          <div className="flex text-[12px] leading-[1.6]">
            {/* Line numbers */}
            <div className="sticky left-0 shrink-0 select-none border-r border-border-subtle bg-elevated/30 px-2 py-2 text-right font-mono text-[11px] text-text-muted/50">
              {lines.map((_, i) => (
                <div key={i}>{i + 1}</div>
              ))}
            </div>
            {/* Code */}
            <pre className="flex-1 overflow-x-auto whitespace-pre px-3 py-2 font-mono text-text-secondary">
              {content}
            </pre>
          </div>
        )}
      </div>

      {/* Footer */}
      {content !== null && (
        <div className="border-t border-border-subtle bg-elevated/50 px-3 py-1.5">
          <div className="flex items-center justify-between text-[10px] text-text-muted">
            <span>{lines.length} lines</span>
            <span>{(content.length / 1024).toFixed(1)} KB</span>
          </div>
        </div>
      )}
    </div>
  );
};
