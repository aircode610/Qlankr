import { useState } from 'react';
import { X, SkipForward, RefreshCw, CheckCircle, MessageSquare } from '@/lib/lucide-icons';
import type { CheckpointData } from '../services/types';

interface CheckpointDialogProps {
  checkpoint: CheckpointData;
  onContinue: (action: 'approve' | 'add_context' | 'skip' | 'rerun', context?: string) => void;
  onDismiss: () => void;
}

export const CheckpointDialog = ({ checkpoint, onContinue, onDismiss }: CheckpointDialogProps) => {
  const [additionalContext, setAdditionalContext] = useState('');
  const [showContextInput, setShowContextInput] = useState(false);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="animate-slide-up w-full max-w-lg rounded-xl border border-border-default bg-elevated shadow-glow">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border-subtle px-5 py-4">
          <div className="flex items-center gap-2">
            <div className="h-2 w-2 animate-pulse rounded-full bg-amber-400" />
            <span className="text-sm font-medium text-text-primary">Human Review Required</span>
          </div>
          <button onClick={onDismiss} className="rounded p-1 text-text-muted transition-colors hover:bg-hover hover:text-text-primary">
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Body */}
        <div className="px-5 py-4">
          <p className="mb-4 text-sm leading-relaxed text-text-secondary">
            {checkpoint.payload?.prompt || `Review results from ${checkpoint.stage_completed} stage.`}
          </p>

          <div className="mb-4 rounded border border-border-subtle bg-deep p-3 text-xs text-text-muted">
            Stage: <span className="text-accent">{checkpoint.stage_completed.replace(/_/g, ' ')}</span>
            {checkpoint.interrupt_type !== 'checkpoint' && (
              <span className="ml-2 text-text-muted">({checkpoint.interrupt_type})</span>
            )}
          </div>

          {checkpoint.payload?.options && (
            <div className="mb-4 text-xs text-text-muted">
              Options: {(checkpoint.payload.options as string[]).join(', ')}
            </div>
          )}

          {showContextInput && (
            <div className="mb-4">
              <textarea
                value={additionalContext}
                onChange={(e) => setAdditionalContext(e.target.value)}
                placeholder="Add context, clarifications, or specific requirements..."
                rows={3}
                className="w-full rounded border border-border-subtle bg-deep px-3 py-2 text-xs text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none"
                autoFocus
              />
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex flex-wrap gap-2 border-t border-border-subtle px-5 py-4">
          <button
            onClick={() => onContinue('approve')}
            className="flex items-center gap-2 rounded-lg bg-emerald-500/20 px-4 py-2 text-sm font-medium text-emerald-400 transition-colors hover:bg-emerald-500/30"
          >
            <CheckCircle className="h-4 w-4" />
            Approve &amp; Continue
          </button>

          <button
            onClick={() => {
              if (!showContextInput) { setShowContextInput(true); return; }
              onContinue('add_context', additionalContext || undefined);
            }}
            className="flex items-center gap-2 rounded-lg bg-accent/20 px-4 py-2 text-sm font-medium text-accent transition-colors hover:bg-accent/30"
          >
            <MessageSquare className="h-4 w-4" />
            {showContextInput ? 'Submit Context' : 'Add Context'}
          </button>

          <button
            onClick={() => onContinue('rerun')}
            className="flex items-center gap-2 rounded-lg border border-border-subtle bg-elevated px-4 py-2 text-sm text-text-secondary transition-colors hover:bg-hover hover:text-text-primary"
          >
            <RefreshCw className="h-4 w-4" />
            Rerun Stage
          </button>

          <button
            onClick={() => onContinue('skip')}
            className="flex items-center gap-2 rounded-lg border border-border-subtle bg-elevated px-4 py-2 text-sm text-text-secondary transition-colors hover:bg-hover hover:text-text-primary"
          >
            <SkipForward className="h-4 w-4" />
            Skip
          </button>
        </div>
      </div>
    </div>
  );
};
