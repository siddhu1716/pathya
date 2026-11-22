/** The Sanskrit name in Telugu script, with a Latin reading alongside it. */
export function Wordmark() {
  return (
    <span className="inline-flex flex-col items-start">
      <span className="wordmark" role="img" aria-label="Pathya">
        <span lang="sa-Telu">పథ్య</span><span aria-hidden="true">Pathya</span>
      </span>
      <span className="text-xs leading-4 text-muted-foreground">From meals to medicines</span>
    </span>
  );
}
