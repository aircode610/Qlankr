import { Layers, Map } from '@/lib/lucide-icons';

interface ChoiceDialogProps {
  onChoice: (choice: 'integration' | 'e2e') => void;
}

export const ChoiceDialog = ({ onChoice }: ChoiceDialogProps) => {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="animate-slide-up w-full max-w-md rounded-xl border border-border-default bg-elevated shadow-glow">
        <div className="px-5 py-4">
          <p className="text-sm font-medium text-text-primary">What should we test next?</p>
          <p className="mt-1 text-[11px] text-text-muted">Unit tests approved. Choose the next stage.</p>
        </div>

        <div className="flex flex-col gap-2 px-5 pb-5">
          <button
            onClick={() => onChoice('integration')}
            className="group flex items-center gap-3 rounded-lg border border-border-subtle bg-deep px-4 py-3 text-left transition-all hover:border-cyan-500/40 hover:bg-cyan-500/5"
          >
            <div className="rounded-lg bg-cyan-500/15 p-2">
              <Layers className="h-5 w-5 text-cyan-400" />
            </div>
            <div>
              <p className="text-xs font-medium text-text-primary">Integration Tests</p>
              <p className="text-[10px] text-text-muted">Find cross-module integration points and generate test specs</p>
            </div>
          </button>

          <button
            onClick={() => onChoice('e2e')}
            className="group flex items-center gap-3 rounded-lg border border-border-subtle bg-deep px-4 py-3 text-left transition-all hover:border-emerald-500/40 hover:bg-emerald-500/5"
          >
            <div className="rounded-lg bg-emerald-500/15 p-2">
              <Map className="h-5 w-5 text-emerald-400" />
            </div>
            <div>
              <p className="text-xs font-medium text-text-primary">E2E Planning</p>
              <p className="text-[10px] text-text-muted">Trace user journeys and plan end-to-end test scenarios</p>
            </div>
          </button>
        </div>
      </div>
    </div>
  );
};
