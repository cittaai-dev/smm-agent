export function WorkspaceProfileCard() {
  return (
    <div className="rounded-lg border border-border bg-surface2 p-3.5">
      <div className="mb-2 font-mono text-[10.5px] tracking-wide text-text-faint">WORKSPACE PROFILE</div>
      <div className="flex justify-between py-0.5 text-xs">
        <span className="text-text-dim">Scope</span>
        <span>this brand only</span>
      </div>
      <div className="flex justify-between py-0.5 text-xs">
        <span className="text-text-dim">Trust</span>
        <span className="text-run">brand-provided</span>
      </div>
      <div className="flex justify-between py-0.5 text-xs">
        <span className="text-text-dim">Lifetime</span>
        <span>refreshed each cycle</span>
      </div>
    </div>
  );
}
