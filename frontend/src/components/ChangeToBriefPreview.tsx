export function ChangeToBriefPreview() {
  return (
    <figure
      className="change-proof"
      aria-label="A pricing page change becoming an Outpace intelligence brief"
    >
      <figcaption>
        <div>
          <span className="change-proof__dot" />
          <strong>Proof of change</strong>
        </div>
        <span>Live product demonstration</span>
      </figcaption>

      <div className="change-proof__rail">
        <span className="is-active">Snapshot</span>
        <span>Evidence</span>
        <span>Decision brief</span>
      </div>

      <div className="change-proof__content">
        <section className="change-proof__diff">
          <header>
            <div>
              <span>Pricing page</span>
              <strong>Demo Analytics Company</strong>
            </div>
            <span>12 minutes ago</span>
          </header>

          <div className="diff-comparison">
            <div className="diff-column diff-column--old">
              <span>Previous snapshot</span>
              <p>Pro plan</p>
              <p className="diff-line diff-line--removed">
                $79 / month
              </p>
              <p className="diff-line diff-line--removed">
                1,000 AI tasks
              </p>
            </div>

            <div className="diff-column diff-column--new">
              <span>Current snapshot</span>
              <p>Pro plan</p>
              <p className="diff-line diff-line--added">
                $99 / month
              </p>
              <p className="diff-line diff-line--added">
                2,000 AI tasks
              </p>
            </div>
          </div>

          <div className="evidence-row">
            <span>2 verified changes</span>
            <span>Source snapshots retained</span>
          </div>
        </section>

        <div className="change-proof__flow" aria-hidden="true">
          <span />
          <strong>Context added</strong>
          <span />
        </div>

        <article className="change-proof__brief">
          <header>
            <div>
              <span>Outpace intelligence brief</span>
              <strong>Pricing · High priority</strong>
            </div>
            <span className="brief-seal">Ready</span>
          </header>

          <div>
            <span>Decision signal</span>
            <h2>
              Pricing increased as product capacity doubled.
            </h2>
            <p>
              The competitor is testing higher willingness to pay
              while strengthening the value story around AI usage.
            </p>
          </div>

          <footer>
            <span>
              <strong>Why it matters</strong>
              Upmarket positioning may be accelerating.
            </span>
            <span>
              <strong>Next move</strong>
              Review packaging and account-level talk tracks.
            </span>
          </footer>
        </article>
      </div>

      <div className="change-proof__footnote">
        <span>Sample product flow</span>
        <span>Evidence linked to every conclusion</span>
      </div>
    </figure>
  )
}
