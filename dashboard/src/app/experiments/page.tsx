export default function ExperimentsPage() {
  return (
    <div className="max-w-4xl mx-auto">
      <h2 className="text-xl font-bold mb-4">Experiments</h2>
      <div className="bg-card rounded-xl border border-border p-8 text-center">
        <p className="text-muted-foreground">No experiments running yet.</p>
        <p className="text-sm text-muted-foreground mt-1">
          Experiments let you test content hypotheses with controlled A/B comparisons.
        </p>
      </div>
    </div>
  );
}
